"""Build the static EquationBench leaderboard from run artifacts."""

from __future__ import annotations

import csv
import io
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import (
    BENCHMARK_NAME,
    DATASET_VERSION,
    FAMILIES,
    FAMILY_LABELS,
    LEVEL_LABELS,
    __version__,
)
from .dataset import DatasetBundle, load_dataset
from .providers import load_models
from .runner import slugify
from .scoring import (
    paired_bootstrap,
    pairwise_tests,
    score_predictions,
    task_difficulty,
)
from .types import Prediction, Task


@dataclass
class RunRecord:
    run_id: str
    directory: Path
    meta: dict[str, Any]
    predictions: list[Prediction]
    selected_ids: list[str]
    dataset_hash: str
    model_key: str
    coverage: float
    full_coverage: bool
    status: str
    finished_at: str


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _load_predictions(path: Path) -> list[Prediction]:
    predictions: list[Prediction] = []
    if not path.exists():
        return predictions
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            predictions.append(Prediction.from_dict(json.loads(line)))
        except (json.JSONDecodeError, KeyError):
            continue
    return predictions


def load_run_records(runs_dir: Path, tasks_by_id: dict[str, Task]) -> list[RunRecord]:
    records: list[RunRecord] = []
    if not runs_dir.exists():
        return records
    for directory in sorted(path for path in runs_dir.iterdir() if path.is_dir()):
        meta = _load_json(directory / "run.json")
        if not meta:
            continue
        predictions = _load_predictions(directory / "predictions.jsonl")
        by_id = {p.task_id: p for p in predictions}
        selected = list(meta.get("dataset", {}).get("selected_tasks", []))
        if not selected:
            selected = [task_id for task_id in tasks_by_id if task_id in by_id]
        dataset_hash = str(meta.get("dataset", {}).get("dataset_sha256", ""))
        model_key = str(meta.get("model", {}).get("key", directory.name))
        coverage = (sum(1 for task_id in selected if task_id in by_id) / len(selected)) if selected else 0.0
        full = set(selected) == set(tasks_by_id) and all(
            task_id in by_id for task_id in tasks_by_id
        )
        status = str(meta.get("status", "unknown"))
        finished = str(meta.get("finished_at") or "")
        records.append(
            RunRecord(
                run_id=str(meta.get("run_id") or directory.name),
                directory=directory,
                meta=meta,
                predictions=predictions,
                selected_ids=selected,
                dataset_hash=dataset_hash,
                model_key=model_key,
                coverage=coverage,
                full_coverage=full,
                status=status,
                finished_at=finished,
            )
        )
    return records


def _answer_digits(answer: str) -> int:
    return len(answer.replace("-", "").replace("/", "").replace("[", "").replace("]", "").replace(",", "").replace(" ", ""))


def _aggregate_task_stats(tasks: Iterable[Task]) -> dict[str, Any]:
    tasks = list(tasks)
    prompt_chars = sorted(len(task.prompt) for task in tasks)
    answer_digits = sorted(_answer_digits(task.answer) for task in tasks)

    def percentile(values: list[int], p: float) -> int:
        if not values:
            return 0
        index = min(len(values) - 1, max(0, int(round((len(values) - 1) * p))))
        return values[index]

    return {
        "prompt_chars": {
            "min": prompt_chars[0] if prompt_chars else 0,
            "median": percentile(prompt_chars, 0.5),
            "max": prompt_chars[-1] if prompt_chars else 0,
        },
        "answer_digits": {
            "min": answer_digits[0] if answer_digits else 0,
            "median": percentile(answer_digits, 0.5),
            "max": answer_digits[-1] if answer_digits else 0,
        },
    }


def _samples_for_model(
    predictions: Iterable[Prediction],
    tasks_by_id: dict[str, Task],
    *,
    limit_per_family: int = 2,
) -> list[dict[str, Any]]:
    by_family: dict[str, list[Prediction]] = {}
    for prediction in predictions:
        task = tasks_by_id.get(prediction.task_id)
        if task:
            by_family.setdefault(task.family, []).append(prediction)
    samples: list[dict[str, Any]] = []
    for family in FAMILIES:
        family_predictions = by_family.get(family, [])
        if not family_predictions:
            continue
        # Prefer one correct and one incorrect, at the highest available level.
        correct = sorted(
            [p for p in family_predictions if p.correct],
            key=lambda p: tasks_by_id[p.task_id].level,
            reverse=True,
        )
        incorrect = sorted(
            [p for p in family_predictions if not p.correct],
            key=lambda p: tasks_by_id[p.task_id].level,
            reverse=True,
        )
        chosen = []
        if correct:
            chosen.append(correct[0])
        if incorrect:
            chosen.append(incorrect[0])
        if len(chosen) < limit_per_family:
            for prediction in sorted(
                family_predictions,
                key=lambda p: tasks_by_id[p.task_id].level,
                reverse=True,
            ):
                if prediction not in chosen:
                    chosen.append(prediction)
                if len(chosen) >= limit_per_family:
                    break
        for prediction in chosen[:limit_per_family]:
            task = tasks_by_id[prediction.task_id]
            raw = prediction.raw_response or ""
            samples.append(
                {
                    "task_id": task.task_id,
                    "family": task.family,
                    "family_label": FAMILY_LABELS[task.family],
                    "level": task.level,
                    "answer_type": task.answer_type,
                    "prompt": task.prompt[:1600] + ("…" if len(task.prompt) > 1600 else ""),
                    "expected": task.answer,
                    "parsed": prediction.parsed_answer,
                    "correct": prediction.correct,
                    "status": prediction.parse_status,
                    "raw": (raw[-1800:] if len(raw) > 1800 else raw),
                    "latency_ms": prediction.latency_ms,
                }
            )
    return samples


def _model_payload(
    record: RunRecord,
    tasks: list[Task],
    tasks_by_id: dict[str, Task],
    *,
    model_spec: dict[str, Any],
    summary,
    paired: dict[str, Any],
    rank: int,
    rank_division: int,
    dataset_n: int,
) -> dict[str, Any]:
    meta_model = record.meta.get("model", {})
    actual_thinking = sorted(record.meta.get("actual_thinking_levels", {}).keys())
    notes = model_spec.get("notes") or ""
    division = model_spec.get("division") or "standard"
    cost = summary.total_cost_usd if summary.cost_known else None
    cost_per_100 = summary.cost_per_100 if summary.cost_known else None
    payload = {
        "key": record.model_key,
        "slug": slugify(record.model_key),
        "name": model_spec.get("name") or meta_model.get("name") or record.model_key,
        "lab": model_spec.get("lab") or meta_model.get("lab") or "Unknown",
        "provider": model_spec.get("provider") or meta_model.get("provider") or "",
        "model_id": model_spec.get("model") or meta_model.get("model") or "",
        "division": division,
        "color": model_spec.get("color") or "#b8f36b",
        "notes": notes,
        "rank": rank,
        "rank_division": rank_division,
        "rank_mean": paired["rank_mean"],
        "rank_ci": paired["rank_ci"],
        "win_probability": paired["win_probability"],
        "score": paired["score"],
        "score_ci": paired["score_ci"],
        "accuracy": summary.accuracy,
        "accuracy_ci": list(summary.accuracy_ci),
        "correct": summary.correct,
        "n": summary.n,
        "n_dataset": dataset_n,
        "coverage": (sum(1 for p in record.predictions if p.task_id in tasks_by_id) / dataset_n) if dataset_n else 0.0,
        "coverage_scored": record.coverage,
        "full_coverage": record.full_coverage,
        "preview": not record.full_coverage,
        "status": record.status,
        "by_family": summary.by_family,
        "by_level": summary.by_level,
        "status_counts": summary.status_counts,
        "timeouts": summary.status_counts.get("timeout", 0),
        "provider_errors": summary.status_counts.get("provider_error", 0),
        "refusals": summary.status_counts.get("refusal", 0),
        "unparseable": summary.status_counts.get("unparseable", 0),
        "cost_usd": cost,
        "cost_per_100": cost_per_100,
        "cost_known": summary.cost_known,
        "input_tokens": summary.input_tokens,
        "output_tokens": summary.output_tokens,
        "reasoning_tokens": summary.reasoning_tokens,
        "total_tokens": summary.total_tokens,
        "median_latency_ms": summary.median_latency_ms,
        "p95_latency_ms": summary.p95_latency_ms,
        "thinking_requested": record.meta.get("config", {}).get("thinking_requested"),
        "thinking_actual": actual_thinking,
        "run_id": record.run_id,
        "run_dir": str(record.directory),
        "finished_at": record.finished_at,
        "verified": bool(record.full_coverage and record.status == "complete"),
        "identity_source": "provider-reported",
        "url": f"models/{slugify(record.model_key)}.html",
        "samples": _samples_for_model(record.predictions, tasks_by_id),
    }
    return payload


def _write_csv(path: Path, models: list[dict[str, Any]]) -> None:
    buffer = io.StringIO()
    fields = [
        "rank",
        "model",
        "lab",
        "provider",
        "division",
        "score",
        "ci_low",
        "ci_high",
        "accuracy",
        "correct",
        "n",
        "cost_usd",
        "cost_per_100",
        "median_latency_ms",
        "timeouts",
        "provider_errors",
        "coverage",
        "thinking_actual",
        "run_id",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for model in models:
        writer.writerow(
            {
                "rank": model["rank"],
                "model": model["name"],
                "lab": model["lab"],
                "provider": model["provider"],
                "division": model["division"],
                "score": f"{model['score']:.2f}",
                "ci_low": f"{model['score_ci'][0]:.2f}",
                "ci_high": f"{model['score_ci'][1]:.2f}",
                "accuracy": f"{model['accuracy']:.4f}",
                "correct": model["correct"],
                "n": model["n"],
                "cost_usd": "" if model["cost_usd"] is None else f"{model['cost_usd']:.6f}",
                "cost_per_100": "" if model["cost_per_100"] is None else f"{model['cost_per_100']:.6f}",
                "median_latency_ms": model["median_latency_ms"] or "",
                "timeouts": model["timeouts"],
                "provider_errors": model["provider_errors"],
                "coverage": f"{model['coverage']:.4f}",
                "thinking_actual": ",".join(model["thinking_actual"]),
                "run_id": model["run_id"],
            }
        )
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _write_task_csv(path: Path, tasks: list[Task], difficulty: dict[str, float]) -> None:
    buffer = io.StringIO()
    fields = ["task_id", "family", "level", "empirical_accuracy", "prompt_chars", "answer_digits", "answer_type"]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for task in tasks:
        writer.writerow(
            {
                "task_id": task.task_id,
                "family": task.family,
                "level": task.level,
                "empirical_accuracy": f"{difficulty.get(task.task_id, 0):.4f}",
                "prompt_chars": len(task.prompt),
                "answer_digits": _answer_digits(task.answer),
                "answer_type": task.answer_type,
            }
        )
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _docs_pages(docs_dir: Path, template, env: Environment, root: str) -> list[dict[str, str]]:
    pages = []
    for name, title in [
        ("methodology.md", "Methodology"),
        ("tasks.md", "Task Tracks"),
        ("submission.md", "Submitting a Model"),
        ("leaderboard.md", "Leaderboard Notes"),
    ]:
        path = docs_dir / name
        if not path.exists():
            continue
        html = markdown.markdown(
            path.read_text(encoding="utf-8"),
            extensions=["fenced_code", "tables", "toc"],
        )
        output_name = name.replace(".md", ".html")
        pages.append({"name": output_name, "title": title, "html": html})
    return pages


def build_leaderboard(
    runs_dir: Path | str,
    out_dir: Path | str,
    *,
    title: str = "EquationBench Leaderboard",
    bootstrap_replicates: int = 2000,
    min_coverage: float = 0.95,
    include_preview: bool = False,
    dataset_path: Path | str = Path("datasets/equationbench-v1-test"),
    models_config: Path | str = Path("config/models.toml"),
    families: list[str] | tuple[str, ...] | None = None,
    subset_note: str = "",
) -> dict[str, Any]:
    runs_dir = Path(runs_dir)
    out_dir = Path(out_dir)
    bundle: DatasetBundle = load_dataset(Path(dataset_path))
    tasks_all = bundle.tasks
    available_families = list(dict.fromkeys(task.family for task in tasks_all))
    selected_families = list(families) if families else available_families
    unknown = [family for family in selected_families if family not in available_families]
    if unknown:
        raise ValueError(f"unknown family/families: {unknown}")
    tasks = [task for task in tasks_all if task.family in selected_families]
    if not tasks:
        raise ValueError("family filter selected no tasks")
    all_tasks_by_id = {task.task_id: task for task in tasks_all}
    tasks_by_id = {task.task_id: task for task in tasks}
    dataset_hash = str(bundle.manifest.get("dataset_sha256", ""))

    try:
        model_specs = {model.key: model.to_dict() for model in load_models(models_config)}
    except (OSError, ValueError):
        model_specs = {}

    records = load_run_records(runs_dir, all_tasks_by_id)
    warnings: list[str] = []
    eligible: dict[str, RunRecord] = {}
    for record in records:
        if record.dataset_hash != dataset_hash:
            warnings.append(
                f"{record.run_id}: dataset hash mismatch (run {record.dataset_hash[:12]}, expected {dataset_hash[:12]})"
            )
            continue
        if record.status != "complete":
            warnings.append(f"{record.run_id}: run status is {record.status}")
            continue
        provider_errors = sum(
            1 for prediction in record.predictions if prediction.parse_status == "provider_error"
        )
        if provider_errors:
            warnings.append(
                f"{record.run_id}: {provider_errors} provider-error prediction(s); not eligible"
            )
            continue
        if record.coverage < min_coverage:
            warnings.append(f"{record.run_id}: coverage {record.coverage:.0%} below {min_coverage:.0%}")
            continue
        if not record.full_coverage and not include_preview:
            warnings.append(
                f"{record.run_id}: partial set ({len(record.selected_ids)}/{len(tasks)} tasks); use --include-preview to show it"
            )
            continue
        if not record.predictions or all(
            p.parse_status in ("provider_error", "timeout", "missing")
            for p in record.predictions
        ):
            warnings.append(f"{record.run_id}: no usable model responses (all provider errors/timeouts)")
            continue
        previous = eligible.get(record.model_key)
        if previous is None or record.finished_at > previous.finished_at:
            eligible[record.model_key] = record
    if not eligible:
        raise ValueError(
            "no eligible runs found. Run models on the selected dataset first, or pass --include-preview."
        )

    standard_keys = [
        key for key, record in eligible.items()
        if (model_specs.get(key, {}).get("division") or "standard") == "standard"
    ]
    if not include_preview:
        # Keep open-division models out of the official ranking by default.
        eligible = {key: record for key, record in eligible.items() if key in standard_keys}
    if not eligible:
        raise ValueError("no eligible standard-division runs found")

    # Score every included model on the same task set. For full official runs
    # this is the complete fixed set. For preview runs it is the intersection
    # of the tasks those runs covered, so a 35-task preview is not diluted by
    # the 35 unseen tasks.
    common_ids = set(tasks_by_id)
    for record in eligible.values():
        common_ids &= set(record.selected_ids)
    common_tasks = [task for task in tasks if task.task_id in common_ids]
    if not common_tasks:
        raise ValueError("included runs have no common tasks")
    common_ids = set(task.task_id for task in common_tasks)
    predictions_by_model = {
        key: [p for p in record.predictions if p.task_id in common_ids]
        for key, record in eligible.items()
    }
    summaries = {
        key: score_predictions(
            predictions,
            common_tasks,
            bootstrap_replicates=bootstrap_replicates,
            bootstrap_seed=1729,
        )
        for key, predictions in predictions_by_model.items()
    }
    paired = paired_bootstrap(
        predictions_by_model,
        common_tasks,
        replicates=bootstrap_replicates,
        seed=271828,
    )
    tests = pairwise_tests(predictions_by_model, common_tasks)
    difficulty = task_difficulty(predictions_by_model, common_tasks)

    models_payload: list[dict[str, Any]] = []
    for key, record in eligible.items():
        spec = model_specs.get(key, {})
        payload = _model_payload(
            record,
            tasks,
            tasks_by_id,
            model_spec=spec,
            summary=summaries[key],
            paired=paired[key],
            rank=0,
            rank_division=0,
            dataset_n=len(tasks),
        )
        models_payload.append(payload)
    models_payload.sort(key=lambda m: (-m["score"], -m["accuracy"], m["name"]))
    for index, model in enumerate(models_payload, start=1):
        model["rank"] = index
    for division in sorted({m["division"] for m in models_payload}):
        division_models = [m for m in models_payload if m["division"] == division]
        for index, model in enumerate(
            sorted(division_models, key=lambda m: (-m["score"], -m["accuracy"], m["name"])),
            start=1,
        ):
            model["rank_division"] = index

    family_stats = []
    for family in FAMILIES:
        family_tasks = [task for task in common_tasks if task.family == family]
        if not family_tasks:
            continue
        scores = [
            model["by_family"][family]["accuracy"]
            for model in models_payload
            if family in model["by_family"]
        ]
        best_model = max(
            models_payload,
            key=lambda m: m["by_family"].get(family, {}).get("accuracy", -1),
        )
        family_stats.append(
            {
                "key": family,
                "label": FAMILY_LABELS[family],
                "n": len(family_tasks),
                "mean_accuracy": sum(scores) / len(scores) if scores else 0.0,
                "best_model": best_model["name"],
                "best_model_key": best_model["key"],
                "best_accuracy": best_model["by_family"].get(family, {}).get("accuracy", 0.0),
                "description": bundle.manifest.get("families", {}).get(family, {}).get("description", ""),
            }
        )
    level_stats = []
    for level in sorted({task.level for task in common_tasks}):
        level_tasks = [task for task in common_tasks if task.level == level]
        scores = [
            model["by_level"][str(level)]["accuracy"]
            for model in models_payload
            if str(level) in model["by_level"]
        ]
        sizes = {
            task.metadata.get("n")
            for task in level_tasks
            if isinstance(task.metadata.get("n"), int)
        }
        size = next(iter(sizes)) if len(sizes) == 1 else None
        difficulties = {
            float(task.metadata["difficulty"])
            for task in level_tasks
            if isinstance(task.metadata.get("difficulty"), (int, float))
        }
        difficulty_value = next(iter(difficulties)) if len(difficulties) == 1 else None
        level_stats.append(
            {
                "level": level,
                "label": f"L{difficulty_value:g}" if difficulty_value is not None else LEVEL_LABELS[level],
                "difficulty": difficulty_value,
                "size": size,
                "n": len(level_tasks),
                "mean_accuracy": sum(scores) / len(scores) if scores else 0.0,
            }
        )
    # For a size ladder, present the bars in size order rather than level-id order.
    level_stats.sort(key=lambda item: (item["size"] is None, item["size"] or 0, item["level"]))

    benchmark = {
        "name": BENCHMARK_NAME,
        "version": __version__,
        "dataset_version": DATASET_VERSION,
        "dataset_name": bundle.manifest.get("name"),
        "dataset_sha256": dataset_hash,
        "n_tasks": len(tasks),
        "n_tasks_available": len(tasks_all),
        "n_tasks_common": len(common_tasks),
        "track_filter": selected_families
        if (len(available_families) < len(FAMILIES) or len(selected_families) < len(available_families))
        else None,
        "subset_note": subset_note,
        "preview": len(common_tasks) < len(tasks),
        "n_models": len(models_payload),
        "n_standard": sum(1 for m in models_payload if m["division"] == "standard"),
        "n_open": sum(1 for m in models_payload if m["division"] != "standard"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bootstrap_replicates": bootstrap_replicates,
        "metric": "Difficulty-weighted exact pass@1",
        "metric_short": "EQB Score",
        "families": family_stats,
        "levels": level_stats,
        "task_stats": _aggregate_task_stats(common_tasks),
        "divisions": sorted({m["division"] for m in models_payload}),
        "min_coverage": min_coverage,
        "include_preview": include_preview,
        "generator_version": bundle.manifest.get("generator_version"),
        "prompt_version": bundle.manifest.get("prompt_version"),
        "warnings": warnings,
        "pairwise": tests,
        "task_difficulty": [
            {
                "task_id": task.task_id,
                "family": task.family,
                "level": task.level,
                "accuracy": difficulty.get(task.task_id, 0.0),
            }
            for task in common_tasks
        ],
    }
    # Samples make the leaderboard JSON large; keep them in per-model detail
    # files and in the model HTML pages, not in the index payload.
    index_models = [
        {key: value for key, value in model.items() if key != "samples"}
        for model in models_payload
    ]
    data = {"benchmark": benchmark, "models": index_models}

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data").mkdir(exist_ok=True)
    (out_dir / "models").mkdir(exist_ok=True)
    (out_dir / "docs").mkdir(exist_ok=True)
    (out_dir / "data" / "leaderboard.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _write_csv(out_dir / "data" / "leaderboard.csv", models_payload)
    _write_task_csv(out_dir / "data" / "task_difficulty.csv", common_tasks, difficulty)
    (out_dir / "data" / "runs.json").write_text(
        json.dumps(
            [
                {
                    "run_id": record.run_id,
                    "model_key": record.model_key,
                    "status": record.status,
                    "coverage": record.coverage,
                    "finished_at": record.finished_at,
                    "thinking": record.meta.get("actual_thinking_levels", {}),
                    "directory": str(record.directory),
                }
                for record in eligible.values()
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    web_root = Path(__file__).resolve().parent / "web"
    env = Environment(
        loader=FileSystemLoader(web_root / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["num"] = lambda value: f"{int(value):,}"
    index_template = env.get_template("index.html.j2")
    (out_dir / "index.html").write_text(
        index_template.render(
            title=title,
            root="",
            data=data,
            data_json=json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
            benchmark=benchmark,
        ),
        encoding="utf-8",
    )

    model_template = env.get_template("model.html.j2")
    for model in models_payload:
        model_dir = out_dir / "data" / "models"
        model_dir.mkdir(exist_ok=True)
        detail = dict(model)
        (model_dir / f"{model['slug']}.json").write_text(
            json.dumps(detail, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (out_dir / "models" / f"{model['slug']}.html").write_text(
            model_template.render(
                title=f"{model['name']} · {title}",
                root="../",
                model=model,
                benchmark=benchmark,
                model_json=json.dumps(model, ensure_ascii=False).replace("</", "<\\/"),
                benchmark_json=json.dumps(benchmark, ensure_ascii=False).replace("</", "<\\/"),
            ),
            encoding="utf-8",
        )

    docs_template = env.get_template("docs.html.j2")
    docs_dir = Path("docs")
    for page in _docs_pages(docs_dir, None, env, "../"):
        (out_dir / "docs" / page["name"]).write_text(
            docs_template.render(
                title=f"{page['title']} · {title}",
                root="../",
                page_title=page["title"],
                content=page["html"],
                benchmark=benchmark,
            ),
            encoding="utf-8",
        )

    assets_src = web_root / "assets"
    if assets_src.exists():
        shutil.copytree(assets_src, out_dir / "assets", dirs_exist_ok=True)
    preview_note = ""
    if benchmark["preview"]:
        preview_note = (
            f"\n**Preview build:** {benchmark['n_tasks_common']} of {benchmark['n_tasks']} tasks scored. "
            "Not an official full-set release.\n\n"
        )
    (out_dir / "README.md").write_text(
        f"# {title}\n\nGenerated {benchmark['generated_at']} from {benchmark['n_models']} runs "
        f"on {benchmark['n_tasks']} tasks. Open `index.html` or serve the directory with any "
        f"static web server.\n{preview_note}",
        encoding="utf-8",
    )
    return data
