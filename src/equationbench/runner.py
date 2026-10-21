"""Concurrent, resumable benchmark runner."""

from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from . import (
    BENCHMARK_NAME,
    DATASET_VERSION,
    FAMILIES,
    GENERATOR_VERSION,
    PROMPT_VERSION,
)
from .dataset import DatasetBundle
from .prompts import SYSTEM_PROMPT, prompt_fingerprint
from .providers import make_provider
from .providers.base import Provider
from .scoring import ScoreSummary, score_predictions
from .types import Completion, ModelSpec, Prediction, Task, sha256_text
from .verify import grade_response

FAMILY_ORDER = {family: index for index, family in enumerate(FAMILIES)}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "run"


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _atomic_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def select_tasks(
    tasks: Sequence[Task],
    *,
    families: Sequence[str] | None = None,
    levels: Sequence[int] | None = None,
    limit: int | None = None,
) -> list[Task]:
    filtered = [
        task
        for task in tasks
        if (not families or task.family in families) and (not levels or task.level in levels)
    ]
    if limit is None or limit >= len(filtered):
        return filtered
    # Balanced round-robin across (family, level) cells. Cells are ordered
    # level-major so a small run still covers every family at the easier levels
    # before adding deeper levels.
    groups: dict[tuple[str, int], list[Task]] = {}
    for task in filtered:
        groups.setdefault((task.family, task.level), []).append(task)
    ordered_cells = sorted(
        groups,
        key=lambda key: (key[1], FAMILY_ORDER.get(key[0], 99), key[0]),
    )
    selected: list[Task] = []
    offset = 0
    while len(selected) < limit:
        progressed = False
        for key in ordered_cells:
            if len(selected) >= limit:
                break
            if offset < len(groups[key]):
                selected.append(groups[key][offset])
                progressed = True
        if not progressed:
            break
        offset += 1
    return selected


def _is_refusal(text: str) -> bool:
    lowered = text.lower()
    patterns = [
        "i can't assist",
        "i cannot assist",
        "i can't help",
        "i cannot help",
        "i'm unable to",
        "i am unable to",
        "as an ai",
        "i won't",
    ]
    return any(pattern in lowered for pattern in patterns)


@dataclass
class RunConfig:
    model: ModelSpec
    dataset: DatasetBundle
    out_dir: Path | None = None
    concurrency: int = 4
    timeout: float | None = 900.0
    retries: int = 2
    thinking: str | None = None
    families: list[str] | None = None
    levels: list[int] | None = None
    limit: int | None = None
    force: bool = False
    max_cost: float | None = None
    notes: str = ""
    system_prompt: str = SYSTEM_PROMPT
    provider: Provider | None = None
    on_progress: Callable[[int, int, Prediction], None] | None = None


@dataclass
class RunResult:
    run_id: str
    run_dir: Path
    summary: ScoreSummary
    predictions: list[Prediction]
    status: str
    aborted_reason: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "status": self.status,
            "aborted_reason": self.aborted_reason,
            "summary": self.summary.to_dict(),
            "metadata": self.metadata,
        }


def _prediction_from_error(
    task: Task, model_key: str, completion: Completion, attempts: int, started_at: str
) -> Prediction:
    status = "timeout" if completion.error_kind == "timeout" else "provider_error"
    return Prediction(
        task_id=task.task_id,
        model_key=model_key,
        raw_response=completion.text or "",
        parsed_answer=None,
        correct=False,
        parse_status=status,
        error=completion.error,
        latency_ms=completion.latency_ms,
        usage=completion.usage,
        cost_usd=completion.cost_usd,
        attempts=attempts,
        model_info=completion.model_info,
        stop_reason=completion.stop_reason,
        started_at=started_at,
        finished_at=utc_now(),
    )


def _prediction_from_completion(
    task: Task, model_key: str, completion: Completion, attempts: int, started_at: str
) -> Prediction:
    if completion.error:
        return _prediction_from_error(task, model_key, completion, attempts, started_at)
    graded = grade_response(completion.text, task.answer, task.answer_type)
    status = graded.status
    if not graded.correct and status == "unparseable" and _is_refusal(completion.text):
        status = "refusal"
    return Prediction(
        task_id=task.task_id,
        model_key=model_key,
        raw_response=completion.text,
        parsed_answer=graded.parsed_answer,
        correct=graded.correct,
        parse_status=status,
        error=graded.error,
        latency_ms=completion.latency_ms,
        usage=completion.usage,
        cost_usd=completion.cost_usd,
        attempts=attempts,
        model_info=completion.model_info,
        stop_reason=completion.stop_reason,
        started_at=started_at,
        finished_at=utc_now(),
    )


def _load_predictions(path: Path) -> list[Prediction]:
    if not path.exists():
        return []
    predictions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            predictions.append(Prediction.from_dict(json.loads(line)))
        except (json.JSONDecodeError, KeyError):
            continue
    return predictions


def run_benchmark(config: RunConfig) -> RunResult:
    model = config.model
    timeout = config.timeout if config.timeout and config.timeout > 0 else None
    if config.thinking:
        model = ModelSpec(**{**model.__dict__, "thinking": config.thinking})
    tasks = select_tasks(
        config.dataset.tasks,
        families=config.families,
        levels=config.levels,
        limit=config.limit,
    )
    if not tasks:
        raise ValueError("no tasks selected")
    selected_ids = [task.task_id for task in tasks]

    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{slugify(model.key)}-{sha256_text(str(selected_ids))[:8]}"
    run_dir = config.out_dir or Path("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = run_dir / "predictions.jsonl"
    run_path = run_dir / "run.json"
    summary_path = run_dir / "summary.json"

    existing = [] if config.force else _load_predictions(predictions_path)
    if config.force:
        predictions_path.write_text("", encoding="utf-8")
    else:
        # Provider errors are infrastructure failures, not model answers. Drop
        # them on resume so the affected tasks are retried instead of being
        # permanently cached as wrong.
        retained = [p for p in existing if p.parse_status != "provider_error"]
        if len(retained) != len(existing):
            with predictions_path.open("w", encoding="utf-8") as handle:
                for prediction in retained:
                    handle.write(json.dumps(prediction.to_dict(), ensure_ascii=False) + "\n")
        existing = retained
    existing_ids = {p.task_id for p in existing}
    pending = [task for task in tasks if task.task_id not in existing_ids]

    started_at = utc_now()
    provider = config.provider or make_provider(model)
    abort = threading.Event()
    abort_reason: list[str] = []
    write_lock = threading.Lock()
    progress_lock = threading.Lock()
    done_count = len(existing)
    total = len(tasks)
    cost_so_far = sum(p.cost_usd or 0.0 for p in existing)
    fatal_kinds = {"billing", "auth", "bad_model", "usage_limit"}

    run_meta = {
        "benchmark": BENCHMARK_NAME,
        "dataset_version": DATASET_VERSION,
        "generator_version": GENERATOR_VERSION,
        "prompt_version": PROMPT_VERSION,
        "prompt_fingerprint": sha256_text(prompt_fingerprint()),
        "system_prompt_sha256": sha256_text(config.system_prompt),
        "run_id": run_id,
        "model": model.to_dict(),
        "dataset": {
            "name": config.dataset.manifest.get("name"),
            "path": str(config.dataset.path),
            "dataset_sha256": config.dataset.manifest.get("dataset_sha256"),
            "manifest": config.dataset.manifest,
            "selected_tasks": selected_ids,
        },
        "config": {
            "concurrency": config.concurrency,
            "timeout": timeout,
            "retries": config.retries,
            "thinking_requested": model.thinking,
            "limit": config.limit,
            "families": config.families,
            "levels": config.levels,
            "max_cost": config.max_cost,
            "notes": config.notes,
            "system_prompt": config.system_prompt,
        },
        "environment": {
            "host": platform.node(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "argv": sys.argv,
            "git_commit": _git_commit(),
        },
        "started_at": started_at,
        "finished_at": None,
        "status": "running",
        "aborted_reason": None,
        "n_selected": total,
        "n_existing_at_start": len(existing),
    }
    _atomic_json(run_path, run_meta)

    def worker(task: Task) -> Prediction:
        if abort.is_set():
            return _prediction_from_error(
                task,
                model.key,
                Completion(text="", error=f"run aborted: {abort_reason[0] if abort_reason else 'fatal error'}", error_kind="aborted"),
                0,
                utc_now(),
            )
        started = utc_now()
        last: Completion | None = None
        attempts = 0
        for attempt in range(config.retries + 1):
            attempts = attempt + 1
            try:
                completion = provider.complete(config.system_prompt, task.prompt, timeout)
            except Exception as exc:  # pragma: no cover - provider-specific failures
                completion = Completion(
                    text="",
                    latency_ms=0,
                    error=f"provider raised {type(exc).__name__}: {exc}",
                    error_kind="provider_error",
                )
            last = completion
            if not completion.error:
                return _prediction_from_completion(task, model.key, completion, attempts, started)
            kind = completion.error_kind or "provider_error"
            if kind in fatal_kinds:
                abort.set()
                abort_reason.append(f"{kind}: {completion.error}")
                break
            retryable = kind in {"timeout", "rate_limit", "transient", "empty", "provider_error"}
            if not retryable or attempt >= config.retries:
                break
            sleep_for = min(30.0, 2.0 ** attempt)
            if kind == "rate_limit":
                sleep_for = max(sleep_for, 5.0)
            time.sleep(sleep_for)
        assert last is not None
        return _prediction_from_error(task, model.key, last, attempts, started)

    with ThreadPoolExecutor(max_workers=max(1, config.concurrency)) as executor:
        futures = {executor.submit(worker, task): task for task in pending}
        for future in as_completed(futures):
            prediction = future.result()
            with write_lock:
                with predictions_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(prediction.to_dict(), ensure_ascii=False) + "\n")
                if prediction.cost_usd:
                    cost_so_far += prediction.cost_usd
                if prediction.parse_status in ("provider_error", "timeout") and prediction.error:
                    if any(kind in prediction.error.lower() for kind in ("insufficient_balance", "402 payment required")):
                        abort.set()
                        abort_reason.append(prediction.error)
                if config.max_cost is not None and cost_so_far > config.max_cost:
                    abort.set()
                    abort_reason.append(
                        f"cost limit reached: ${cost_so_far:.4f} > ${config.max_cost:.4f}"
                    )
            with progress_lock:
                done_count += 1
                if config.on_progress:
                    config.on_progress(done_count, total, prediction)
            if abort.is_set():
                # Cancel futures that have not started. Running calls finish.
                for pending_future in futures:
                    pending_future.cancel()

    predictions = _load_predictions(predictions_path)
    prediction_by_id = {p.task_id: p for p in predictions}
    # Keep only predictions for the selected task set, in dataset order.
    selected_predictions = [prediction_by_id[task.task_id] for task in tasks if task.task_id in prediction_by_id]
    summary = score_predictions(selected_predictions, tasks)
    actual_levels = Counter(
        p.model_info.get("thinkingLevel") for p in selected_predictions if p.model_info.get("thinkingLevel")
    )
    status = "complete"
    if len(selected_predictions) < total:
        status = "incomplete"
    if summary.status_counts.get("provider_error", 0) > 0:
        # Provider errors are infrastructure failures, not model answers. A run
        # with any of them is not eligible for an official leaderboard row.
        status = "incomplete"
    if abort_reason:
        status = "aborted"
    finished_at = utc_now()
    run_meta.update(
        {
            "finished_at": finished_at,
            "status": status,
            "aborted_reason": abort_reason[-1] if abort_reason else None,
            "actual_thinking_levels": dict(actual_levels),
            "n_predictions": len(selected_predictions),
        }
    )
    _atomic_json(run_path, run_meta)
    summary_dict = {
        **run_meta,
        "score": summary.to_dict(),
        "summary": summary.to_dict(),
    }
    _atomic_json(summary_path, summary_dict)
    return RunResult(
        run_id=run_id,
        run_dir=run_dir,
        summary=summary,
        predictions=selected_predictions,
        status=status,
        aborted_reason=abort_reason[-1] if abort_reason else None,
        metadata=run_meta,
    )
