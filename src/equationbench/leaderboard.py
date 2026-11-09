"""Build a reproducible leaderboard from EquationBench run receipts.

The builder never trusts a stored frontier score.  It regenerates the task bank
from the recorded season seed and level set, validates the dataset hash, and
re-scores the raw predictions.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import FRONTIER_SCORING_VERSION, GENERATOR_VERSION, PROMPT_VERSION
from .frontier import FrontierScore
from .frontier_run import bundle_from_receipt, frontier_from_predictions
from .ladder import DEFAULT_SEASON_SEED, LADDER_VERSION
from .runner import load_predictions
from .stats import percentile
from .types import Level, Prediction, Task

DIRECT_PROVIDERS = {"deepseek", "openai"}
RANKED_TIERS = {"official", "provisional"}
MIN_VALID_PER_LEVEL = 3
MIN_COMPLETION = 0.90
MIN_TASKS_PER_LEVEL = 5
BAND_RADIUS = 1
OUTPUT_TOKEN_CAP = 65000

JSON_OUT = Path("data/leaderboard.json")
CSV_OUT = Path("data/leaderboard.csv")
MD_OUT = Path("docs/leaderboard.md")
NOTES_PATH = Path("docs/leaderboard-notes.md")
README_PATH = Path("README.md")
README_TABLE = re.compile(
    r"(<!-- leaderboard:start -->\n).*?(\n<!-- leaderboard:end -->)", flags=re.DOTALL
)

#: Columns copied straight from a row.  Nested and list fields are flattened in
#: :func:`_csv_row`.
CSV_FIELDS = (
    "rank",
    "run_dir",
    "run_id",
    "tier",
    "rankable",
    "official",
    "dataset_hash_ok",
    "status",
    "model_key",
    "model_name",
    "lab",
    "provider",
    "model",
    "effort",
    "levels_tested",
    "tasks_per_level",
    "precision_tasks",
    "precision_levels",
    "n_tasks",
    "valid",
    "correct",
    "accuracy",
    "solved_rate",
    "band_levels",
    "band_correct",
    "band_valid",
    "band_rate",
    "coverage",
    "missing",
    "provider_errors",
    "completion",
    "score",
    "composite",
    "score_ci_low",
    "score_ci_high",
    "size",
    "censored",
    "bound",
    "cost_usd",
    "cost_known",
    "cost_basis",
    "cost_per_100_valid",
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
    "median_latency_ms",
    "p95_latency_ms",
    "reasons",
    "warnings",
    "note",
    "short_note",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(run_dir: Path, root: Path) -> Path:
    return run_dir.relative_to(root) if run_dir.is_relative_to(root) else run_dir


def tier_for_path(path: Path) -> str:
    if "official" in path.parts:
        return "official"
    if "provisional" in path.parts:
        return "provisional"
    return "probe"


def _effort(run: dict[str, Any]) -> str:
    actual = run.get("actual_thinking_levels") or {}
    if actual:
        return ",".join(sorted(str(key) for key in actual if key))
    return str(run.get("config", {}).get("thinking_requested") or "unknown")


@dataclass
class _Tally:
    """Predictions for one run, split into model answers and infra failures."""

    valid: list[Prediction]
    infra: list[Prediction]
    by_level: dict[int, dict[str, int]]


def _tally(tasks: Sequence[Task], by_id: dict[str, Prediction]) -> _Tally:
    tally = _Tally(
        valid=[],
        infra=[],
        by_level=defaultdict(
            lambda: {"valid": 0, "correct": 0, "provider_error": 0, "missing": 0}
        ),
    )
    for task in tasks:
        stats = tally.by_level[task.level]
        prediction = by_id.get(task.task_id)
        if prediction is None:
            stats["missing"] += 1
        elif prediction.is_infra:
            stats["provider_error"] += 1
            tally.infra.append(prediction)
        else:
            stats["valid"] += 1
            stats["correct"] += int(prediction.correct)
            tally.valid.append(prediction)
    return tally


def _infra_warnings(infra: Sequence[Prediction]) -> list[str]:
    warnings = []
    timeouts = sum(1 for prediction in infra if prediction.parse_status == "timeout")
    if timeouts:
        warnings.append(f"{timeouts} provider timeout(s)")
    capped = sum(
        1
        for prediction in infra
        if prediction.stop_reason == "length"
        or int((prediction.usage or {}).get("output") or 0) >= OUTPUT_TOKEN_CAP
    )
    if capped:
        warnings.append(f"{capped} response(s) hit the output token cap")
    return warnings


def _cost_fields(
    run_dir: Path, predictions: Sequence[Prediction], warnings: list[str]
) -> dict[str, Any]:
    """Total cost for a run.  May append a partial-cost warning."""
    costs = [prediction.cost_usd for prediction in predictions]
    missing = sum(1 for cost in costs if cost is None)
    known = bool(costs) and missing == 0
    total = sum(float(cost or 0.0) for cost in costs)
    basis = "provider_reported" if known else "unknown"
    summary_path = run_dir / "summary.json"
    if missing and summary_path.exists():
        try:
            summary_cost = _read_json(summary_path).get("score", {}).get("total_cost_usd")
        except (json.JSONDecodeError, OSError):
            summary_cost = None
        if summary_cost is not None:
            total = float(summary_cost)
            known = True
            basis = "provider_reported_partial"
            warnings.append(f"cost excludes {missing} call(s) with no cost record")
    return {"total": total, "known": known, "basis": basis}


def _usage_totals(predictions: Iterable[Prediction]) -> dict[str, int]:
    totals = {"input": 0, "output": 0, "reasoning": 0, "total": 0}
    for prediction in predictions:
        usage = prediction.usage or {}
        totals["input"] += int(usage.get("input") or 0)
        totals["output"] += int(usage.get("output") or 0)
        totals["reasoning"] += int(usage.get("reasoning") or 0)
        totals["total"] += int(usage.get("totalTokens") or 0)
    return totals


def _level_rows(
    levels: Sequence[Level],
    tasks: Sequence[Task],
    by_level: dict[Level, dict[str, int]],
    score: FrontierScore | None,
) -> list[dict[str, Any]]:
    rows = []
    for level in levels:
        stats = by_level[level]
        payload: dict[str, Any] = {
            "level": level,
            "size": next(
                (task.metadata.get("level_size") for task in tasks if task.level == level),
                None,
            ),
            **stats,
        }
        if stats["valid"]:
            payload["p"] = stats["correct"] / stats["valid"]
        if score is not None:
            fitted = next((row for row in score.levels if row["level"] == level), None)
            if fitted:
                payload["smoothed"] = fitted["smoothed"]
        rows.append(payload)
    return rows


def _unranked_reasons(
    *,
    n_tasks: int,
    n_valid: int,
    status: str,
    completion: float,
    levels_ok: bool,
    score: FrontierScore | None,
    score_is_finite: bool,
) -> list[str]:
    reasons: list[str] = []
    if n_tasks == 0:
        reasons.append("no tasks")
    if n_valid == 0:
        reasons.append("no valid predictions")
    if status != "complete":
        reasons.append(f"run status is {status}")
    if completion < MIN_COMPLETION:
        reasons.append(f"valid completion is {completion:.0%}")
    if not levels_ok:
        reasons.append("at least one used level has fewer than 3 valid tasks")
    if score is None:
        reasons.append("frontier is not estimable")
    elif score.censored:
        reasons.append(f"score is censored ({score.censored})")
    elif score.score is None:
        reasons.append("score is not finite")
    if not score_is_finite and not reasons:
        reasons.append("score is not rankable")
    return reasons


def _band_fields(
    score: FrontierScore | None,
    levels: Sequence[Level],
    by_level: dict[Level, dict[str, int]],
) -> dict[str, Any]:
    """Solve rate over the whole levels within one step of ``floor(EQB-L)``.

    Only whole levels count, so a run with extra half levels gets the same
    window as one without.
    """
    band_levels: list[int] = []
    correct = valid = 0
    if score is not None and score.score is not None:
        centre = math.floor(score.score)
        window = range(centre - BAND_RADIUS, centre + BAND_RADIUS + 1)
        for level in levels:
            stats = by_level[level]
            if level in window and stats["valid"]:
                band_levels.append(level)
                correct += stats["correct"]
                valid += stats["valid"]
    return {
        "band_levels": band_levels,
        "band_correct": correct,
        "band_valid": valid,
        "band_rate": (correct / valid) if valid else None,
    }


def _score_fields(score: FrontierScore | None, band_rate: float | None) -> dict[str, Any]:
    if score is None:
        return {
            "score": None,
            "composite": None,
            "size": None,
            "score_ci": None,
            "size_ci": None,
            "censored": None,
            "bound": None,
            "bound_size": None,
            "scoring_version": None,
        }
    finite = score.score is not None and score.censored is None
    return {
        "score": score.score if score.censored is None else None,
        "composite": score.score * band_rate if finite and band_rate is not None else None,
        "size": score.size,
        "score_ci": list(score.ci) if score.ci else None,
        "size_ci": list(score.size_ci) if score.size_ci else None,
        "censored": score.censored,
        "bound": score.bound,
        "bound_size": score.bound_size,
        "scoring_version": score.scoring_version,
    }


def load_run(run_dir: Path, bootstrap: int, *, root: Path) -> dict[str, Any] | None:
    """Re-score one receipt.  Returns ``None`` if it is not a ladder receipt."""
    run_path = run_dir / "run.json"
    if not run_path.exists():
        return None
    run = _read_json(run_path)
    relative = _relative(run_dir, root)
    try:
        bundle = bundle_from_receipt(run)
    except Exception as exc:  # pragma: no cover - malformed receipt
        return {
            "run_dir": str(relative),
            "run_id": run.get("run_id"),
            "tier": tier_for_path(relative),
            "error": f"task bank rebuild failed: {exc}",
            "rankable": False,
        }
    if bundle is None:
        return None

    manifest = bundle.manifest
    recorded = run.get("dataset", {}).get("manifest") or {}
    levels: list[Level] = manifest["levels_included"]
    tasks_per_level = int(manifest["tasks_per_level"])
    tasks = bundle.tasks
    known_ids = {task.task_id for task in tasks}
    by_id = {p.task_id: p for p in load_predictions(run_dir / "predictions.jsonl")}

    warnings: list[str] = []
    recorded_hash = str(run.get("dataset", {}).get("dataset_sha256") or "")
    dataset_hash_ok = bool(recorded_hash and recorded_hash == manifest["dataset_sha256"])
    if recorded_hash and not dataset_hash_ok:
        warnings.append("dataset hash does not match the regenerated task bank")
    unknown = set(by_id) - known_ids
    if unknown:
        warnings.append(f"{len(unknown)} prediction task ids are outside the task bank")

    tally = _tally(tasks, by_id)
    score: FrontierScore | None
    try:
        score = frontier_from_predictions(tally.valid, tasks, bootstrap_replicates=bootstrap)
    except ValueError as exc:
        warnings.append(f"frontier could not be estimated: {exc}")
        score = None

    n_tasks = len(tasks)
    n_valid = len(tally.valid)
    n_infra = len(tally.infra)
    completion = (n_valid / n_tasks) if n_tasks else 0.0
    correct = sum(1 for prediction in tally.valid if prediction.correct)
    level_rows = _level_rows(levels, tasks, tally.by_level, score)

    warnings.extend(_infra_warnings(tally.infra))
    if score is not None and score.ci is not None and abs(score.ci[1] - score.ci[0]) < 1e-9:
        warnings.append(
            "CI is degenerate: every bracket-level task passed or failed, "
            "so the task bootstrap has no variance"
        )

    attempted = tally.valid + tally.infra
    latencies = [p.latency_ms for p in tally.valid if p.latency_ms]
    cost = _cost_fields(run_dir, attempted, warnings)
    usage = _usage_totals(attempted)

    model = run.get("model", {})
    note = str(run.get("aborted_reason") or run.get("config", {}).get("notes") or "")
    effort = _effort(run)
    tier = tier_for_path(relative)
    route = str(model.get("provider") or "unknown")
    status = str(run.get("status") or "unknown")

    used_levels = [level for level in levels if tally.by_level[level]["valid"]]
    levels_ok = len(used_levels) >= 2 and all(
        tally.by_level[level]["valid"] >= MIN_VALID_PER_LEVEL for level in levels
    )
    score_is_finite = bool(
        score is not None and score.score is not None and score.censored is None
    )
    reasons = _unranked_reasons(
        n_tasks=n_tasks,
        n_valid=n_valid,
        status=status,
        completion=completion,
        levels_ok=levels_ok,
        score=score,
        score_is_finite=score_is_finite,
    )
    common_ok = (
        status == "complete"
        and score_is_finite
        and levels_ok
        and tasks_per_level >= MIN_TASKS_PER_LEVEL
    )
    official_ok = (
        common_ok
        and tier == "official"
        and n_infra == 0
        and completion == 1.0
        and effort == "max"
        and route in DIRECT_PROVIDERS
    )
    provisional_ok = common_ok and tier == "provisional" and completion >= MIN_COMPLETION
    rankable = official_ok or provisional_ok
    if not rankable and not reasons:
        reasons.append("run does not meet the ranked-row rules")

    band = _band_fields(score, levels, tally.by_level)
    return {
        "run_dir": str(relative),
        "run_id": run.get("run_id"),
        "tier": tier,
        "rankable": rankable,
        "official": official_ok,
        "status": status,
        "finished_at": run.get("finished_at"),
        "model": {
            "key": model.get("key"),
            "name": model.get("name"),
            "lab": model.get("lab"),
            "provider": route,
            "model": model.get("model"),
        },
        "effort": effort,
        "cost_basis": cost["basis"],
        "dataset_hash_ok": dataset_hash_ok,
        "levels_tested": levels,
        "tasks_per_level": tasks_per_level,
        "precision_tasks": int(manifest["precision_tasks"]),
        "precision_levels": manifest["precision_levels"],
        "level_task_counts": recorded.get("level_task_counts"),
        "n_tasks": n_tasks,
        "valid": n_valid,
        "correct": correct,
        "accuracy": (correct / n_valid) if n_valid else None,
        "missing": n_tasks - n_valid - n_infra,
        "provider_errors": n_infra,
        "completion": completion,
        "cost_usd": cost["total"] if cost["known"] else None,
        "cost_known": cost["known"],
        "cost_per_100_valid": (
            (cost["total"] / n_valid * 100) if cost["known"] and n_valid else None
        ),
        "input_tokens": usage["input"],
        "output_tokens": usage["output"],
        "reasoning_tokens": usage["reasoning"],
        "total_tokens": usage["total"],
        "median_latency_ms": round(statistics.median(latencies)) if latencies else None,
        "p95_latency_ms": round(p95) if (p95 := percentile(latencies, 0.95)) is not None else None,
        "levels": level_rows,
        "solved_rate": (correct / n_valid) if n_valid else None,
        "coverage": (n_valid / n_tasks) if n_tasks else None,
        "warnings": warnings,
        "reasons": reasons,
        "note": note,
        "short_note": (
            (warnings[0] if warnings else "")
            or (note if not rankable else "")
            or (reasons[0] if reasons else "")
        ),
        **band,
        **_score_fields(score, band["band_rate"]),
    }


def discover_runs(roots: Iterable[Path]) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        if root.exists():
            found.extend(sorted({path.parent for path in root.rglob("run.json")}))
    return found


def _strength(row: dict[str, Any]) -> tuple:
    return (
        1 if row.get("rankable") else 0,
        1 if row.get("score") is not None else 0,
        row.get("n_tasks") or 0,
        row.get("valid") or 0,
        row.get("run_id") or "",
    )


def keep_strongest(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the strongest receipt for a repeated model/effort/route cell."""
    best: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        model = row.get("model", {})
        key = (model.get("key"), row.get("effort"), model.get("provider"))
        if key not in best or _strength(row) > _strength(best[key]):
            best[key] = row
    return list(best.values())


def rank_rows(rows: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Assign ranks in place and return ``(ranked, unranked)``."""
    ranked = sorted(
        [row for row in rows if row.get("rankable") and row.get("composite") is not None],
        key=lambda row: (
            -float(row["composite"]),
            -float(row["score"]),
            -(row.get("solved_rate") or 0.0),
            -(row.get("correct") or 0),
            row.get("cost_per_100_valid") or math.inf,
        ),
    )
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    ranked_ids = {row.get("run_dir") for row in ranked}
    unranked = sorted(
        [row for row in rows if row.get("run_dir") not in ranked_ids],
        key=lambda row: (row.get("model", {}).get("name") or "", row.get("effort") or ""),
    )
    for row in unranked:
        row["rank"] = None
    return ranked, unranked


def build_payload(
    root: Path,
    *,
    bootstrap: int = 2000,
    include_probes: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    run_roots = [root / "runs" / "official", root / "runs" / "provisional"]
    if include_probes:
        run_roots.append(root / "runs" / "probes")
    loaded = (load_run(run_dir, bootstrap, root=root) for run_dir in discover_runs(run_roots))
    ranked, unranked = rank_rows(keep_strongest(row for row in loaded if row is not None))
    ordered = ranked + unranked
    stamps = [row["finished_at"] for row in ordered if row.get("finished_at")]
    return {
        "generated_at": generated_at or (max(stamps) if stamps else "unknown"),
        "generator": "eqb build-leaderboard",
        "season_seed": DEFAULT_SEASON_SEED,
        "ladder_version": LADDER_VERSION,
        "generator_version": GENERATOR_VERSION,
        "prompt_version": PROMPT_VERSION,
        "scoring_version": FRONTIER_SCORING_VERSION,
        "bootstrap_replicates": bootstrap,
        "rules": {
            "min_valid_per_level": MIN_VALID_PER_LEVEL,
            "min_completion": MIN_COMPLETION,
            "ranked_tiers": sorted(RANKED_TIERS),
            "composite": "EQB-C = EQB-L * band_rate",
            "band": "whole levels floor(EQB-L) - 1 to floor(EQB-L) + 1",
            "official_effort": "max",
            "official_providers": sorted(DIRECT_PROVIDERS),
        },
        "ranked_count": len(ranked),
        "unranked_count": len(unranked),
        "rows": ordered,
    }


def score_label(row: dict[str, Any]) -> str:
    bound = row.get("bound")
    if row.get("score") is not None:
        return f"{row['score']:.2f}"
    if row.get("censored") == "upper":
        return f"≥{bound:.1f}" if bound is not None else "≥max"
    if row.get("censored") == "lower":
        return f"<{bound:.1f}" if bound is not None else "<min"
    if row.get("censored") == "ambiguous":
        return f"~{bound:.1f}" if bound is not None else "ambiguous"
    return "—"


def format_cost(row: dict[str, Any]) -> str:
    if not row.get("cost_known"):
        return "unknown"
    if row.get("cost_usd") is None:
        return "—"
    suffix = "*" if row.get("cost_basis") == "provider_reported_partial" else ""
    return f"${row['cost_usd']:.2f}{suffix}"


def compact_tokens(value: Any) -> str:
    if value is None:
        return "—"
    n = int(value)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{round(n / 1_000)}k"
    return str(n)


def markdown_table(rows: Sequence[dict[str, Any]]) -> list[str]:
    lines = [
        "| # | Model | Effort | Status | EQB-C | EQB-L (95% CI) | Solved | Band | Cover | Tokens | Cost | Note |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        name = row.get("model", {}).get("name") or row.get("run_dir")
        receipt = row.get("run_dir") or ""
        linked = f"[{name}]({receipt})" if receipt else name
        rankable = row.get("rankable")
        composite = (
            f"{row['composite']:.2f}" if row.get("composite") is not None and rankable else "—"
        )
        score = score_label(row)
        if score != "—" and not rankable and not row.get("censored"):
            score = f"{score}†"
        ci = row.get("score_ci")
        if ci and rankable:
            score = f"{score} ({ci[0]:.2f}–{ci[1]:.2f})"
        band_levels = row.get("band_levels") or []
        band_rate = row.get("band_rate")
        band = (
            f"{band_rate * 100:.0f}% (L{band_levels[0]}–L{band_levels[-1]})"
            if rankable and band_rate is not None and band_levels
            else "—"
        )
        cover = row.get("coverage")
        cover_label = f"{cover * 100:.0f}%" if cover is not None else "—"
        status = "Official" if row.get("official") else ("Provisional" if rankable else "Unranked")
        note = (row.get("short_note") or "").replace("|", "/")
        solved = f"{row.get('correct', 0)}/{row.get('n_tasks', 0)}"
        cells = [
            row.get("rank") or "—",
            linked,
            row.get("effort") or "—",
            status,
            composite,
            score,
            solved,
            band,
            cover_label,
            compact_tokens(row.get("total_tokens")),
            format_cost(row),
            note,
        ]
        lines.append("| " + " | ".join(str(cell) for cell in cells) + " |")
    return lines


def render_markdown(payload: dict[str, Any], notes: str) -> str:
    """The generated table, followed by the hand-edited notes."""
    head = [
        "# EquationBench Linear Leaderboard",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        f"Season seed `{payload['season_seed']}` · ladder v{payload['ladder_version']} · "
        f"scoring v{payload['scoring_version']}. One table, all runs.",
        "",
        "Web view: <https://woxtom.github.io/equationbench/>",
        "",
        "`EQB-C = EQB-L × Band` is the ranked composite. It rewards a high "
        "frontier and reliability near that frontier. `EQB-L` is the 50% "
        "frontier. `Band` is the exact-solve rate over the whole levels "
        "`floor(EQB-L) - 1` to `floor(EQB-L) + 1`. Testing extra easy or hard "
        "levels does not move that window. `Solved` is exact "
        "answers divided by all tasks. `Cover` is valid tasks divided by all "
        "tasks. Provider errors are excluded from the rate, but they lower the "
        "coverage.",
        "",
    ]
    return "\n".join(head + markdown_table(payload["rows"])) + "\n\n" + notes.strip() + "\n"


def _csv_row(row: dict[str, Any]) -> dict[str, Any]:
    model = row.get("model", {})
    ci = row.get("score_ci") or [None, None]
    joined = {
        key: ",".join(str(level) for level in row.get(key) or [])
        for key in ("levels_tested", "precision_levels", "band_levels")
    }
    return {
        **{field: row.get(field) for field in CSV_FIELDS},
        **joined,
        "model_key": model.get("key"),
        "model_name": model.get("name"),
        "lab": model.get("lab"),
        "provider": model.get("provider"),
        "model": model.get("model"),
        "score_ci_low": ci[0],
        "score_ci_high": ci[1],
        "reasons": "; ".join(row.get("reasons") or []),
        "warnings": "; ".join(row.get("warnings") or []),
    }


def render_csv(rows: Iterable[dict[str, Any]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows(_csv_row(row) for row in rows)
    return buffer.getvalue()


def render_readme(readme: str, rows: Sequence[dict[str, Any]]) -> str:
    """Replace the table between the README's leaderboard markers."""
    if not README_TABLE.search(readme):
        raise ValueError("README has no leaderboard markers")
    table = "\n".join(markdown_table(rows))
    return README_TABLE.sub(lambda match: match.group(1) + table + match.group(2), readme)


def render_outputs(
    root: Path,
    payload: dict[str, Any],
    *,
    json_out: Path = JSON_OUT,
    csv_out: Path = CSV_OUT,
    md_out: Path = MD_OUT,
) -> dict[Path, bytes]:
    """Every generated file, as exact bytes, keyed by absolute path."""
    notes = (root / NOTES_PATH).read_text(encoding="utf-8")
    readme = (root / README_PATH).read_text(encoding="utf-8")
    rendered = {
        json_out: json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        csv_out: render_csv(payload["rows"]),
        md_out: render_markdown(payload, notes),
        README_PATH: render_readme(readme, payload["rows"]),
    }
    return {root / path: text.encode("utf-8") for path, text in rendered.items()}


def stale_outputs(outputs: dict[Path, bytes]) -> list[Path]:
    """Generated files whose on-disk bytes differ from a fresh build."""
    return [
        path
        for path, content in outputs.items()
        if not path.exists() or path.read_bytes() != content
    ]


def write_outputs(outputs: dict[Path, bytes]) -> None:
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
