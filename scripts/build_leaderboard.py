#!/usr/bin/env python3
"""Build a reproducible leaderboard from EquationBench run receipts.

The builder never trusts a stored frontier score.  It regenerates the task bank
from the recorded season seed and level set, validates the dataset hash, and
re-scores the raw predictions.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from equationbench.frontier import FrontierScore  # noqa: E402
from equationbench.frontier_run import build_ladder_bundle  # noqa: E402
from equationbench.types import Prediction  # noqa: E402

DIRECT_PROVIDERS = {"deepseek", "openai"}
RANKED_TIERS = {"official", "provisional"}
MIN_VALID_PER_LEVEL = 3
MIN_COMPLETION = 0.90


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_predictions(path: Path) -> list[Prediction]:
    if not path.exists():
        return []
    rows: list[Prediction] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(Prediction.from_dict(json.loads(line)))
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return rows


def percentile(values: list[int], p: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return round(ordered[lower] * (1 - fraction) + ordered[upper] * fraction)


def as_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def tier_for_path(path: Path) -> str:
    parts = path.parts
    if "official" in parts:
        return "official"
    if "provisional" in parts:
        return "provisional"
    return "probe"


def effort_for_run(run: dict[str, Any]) -> str:
    actual = run.get("actual_thinking_levels") or {}
    if actual:
        return ",".join(sorted(str(key) for key in actual if key))
    return str(run.get("config", {}).get("thinking_requested") or "unknown")


def route_for_run(run: dict[str, Any]) -> str:
    model = run.get("model", {})
    return str(model.get("provider") or "unknown")


def load_run(run_dir: Path, bootstrap: int) -> dict[str, Any] | None:
    run_path = run_dir / "run.json"
    if not run_path.exists():
        return None
    run = read_json(run_path)
    manifest = run.get("dataset", {}).get("manifest") or {}
    levels = manifest.get("levels_included")
    if levels is None:
        levels = [row.get("level") for row in manifest.get("levels", [])]
    levels = sorted({int(level) for level in (levels or []) if level is not None})
    tasks_per_level = int(manifest.get("tasks_per_level") or 0)
    precision_tasks = int(manifest.get("precision_tasks") or 0)
    precision_levels = manifest.get("precision_levels") or []
    if not levels or tasks_per_level < 1:
        return None
    season_seed = manifest.get("season_seed")
    if season_seed is None:
        season_seed = run.get("config", {}).get("season_seed")
    if season_seed is None:
        return None

    try:
        bundle = build_ladder_bundle(
            levels,
            tasks_per_level=tasks_per_level,
            precision_levels=precision_levels,
            precision_tasks=precision_tasks,
            season_seed=season_seed,
        )
    except Exception as exc:  # pragma: no cover - malformed receipt
        return {
            "run_dir": str(run_dir.relative_to(ROOT)) if run_dir.is_relative_to(ROOT) else str(run_dir),
            "run_id": run.get("run_id"),
            "tier": tier_for_path(run_dir.relative_to(ROOT) if run_dir.is_relative_to(ROOT) else run_dir),
            "error": f"task bank rebuild failed: {exc}",
            "rankable": False,
        }

    tasks_by_id = {task.task_id: task for task in bundle.tasks}
    predictions = read_predictions(run_dir / "predictions.jsonl")
    pred_by_id = {prediction.task_id: prediction for prediction in predictions}

    warnings: list[str] = []
    recorded_hash = str(run.get("dataset", {}).get("dataset_sha256") or "")
    expected_hash = str(bundle.manifest.get("dataset_sha256") or "")
    dataset_hash_ok = bool(recorded_hash and recorded_hash == expected_hash)
    if recorded_hash and not dataset_hash_ok:
        warnings.append("dataset hash does not match the regenerated task bank")
    unknown_ids = sorted(set(pred_by_id) - set(tasks_by_id))
    if unknown_ids:
        warnings.append(f"{len(unknown_ids)} prediction task ids are outside the task bank")

    selected_tasks = [tasks_by_id[task_id] for task_id in tasks_by_id]
    valid_predictions: list[Prediction] = []
    infra_predictions: list[Prediction] = []
    level_stats: dict[int, dict[str, int]] = defaultdict(
        lambda: {"valid": 0, "correct": 0, "provider_error": 0, "missing": 0}
    )
    for task in selected_tasks:
        stats = level_stats[task.level]
        prediction = pred_by_id.get(task.task_id)
        if prediction is None:
            stats["missing"] += 1
            continue
        if prediction.parse_status in ("provider_error", "timeout"):
            stats["provider_error"] += 1
            infra_predictions.append(prediction)
            continue
        stats["valid"] += 1
        if prediction.correct:
            stats["correct"] += 1
        valid_predictions.append(prediction)

    from equationbench.frontier_run import frontier_from_predictions

    try:
        score: FrontierScore = frontier_from_predictions(
            valid_predictions,
            selected_tasks,
            bootstrap_replicates=bootstrap,
        )
    except ValueError as exc:
        warnings.append(f"frontier could not be estimated: {exc}")
        score = None

    n_tasks = len(selected_tasks)
    n_valid = len(valid_predictions)
    n_infra = len(infra_predictions)
    n_missing = n_tasks - n_valid - n_infra
    completion = (n_valid / n_tasks) if n_tasks else 0.0
    correct = sum(1 for prediction in valid_predictions if prediction.correct)

    if n_infra:
        timeouts = sum(1 for prediction in infra_predictions if prediction.parse_status == "timeout")
        if timeouts:
            warnings.append(f"{timeouts} provider timeout(s)")
        capped = sum(
            1
            for prediction in infra_predictions
            if prediction.stop_reason == "length"
            or int((prediction.usage or {}).get("output") or 0) >= 65000
        )
        if capped:
            warnings.append(f"{capped} response(s) hit the output token cap")

    level_rows = []
    for level in levels:
        stats = level_stats[level]
        payload: dict[str, Any] = {
            "level": level,
            "size": next((task.metadata.get("level_size") for task in selected_tasks if task.level == level), None),
            **stats,
        }
        if stats["valid"]:
            payload["p"] = stats["correct"] / stats["valid"]
        if score is not None:
            fitted = next((row for row in score.levels if row["level"] == level), None)
            if fitted:
                payload["smoothed"] = fitted["smoothed"]
        level_rows.append(payload)

    if score is not None and score.ci is not None:
        if abs(score.ci[1] - score.ci[0]) < 1e-9:
            warnings.append(
                "CI is degenerate: every bracket-level task passed or failed, "
                "so the task bootstrap has no variance"
            )

    latencies = [prediction.latency_ms for prediction in valid_predictions if prediction.latency_ms]
    costs = [prediction.cost_usd for prediction in valid_predictions + infra_predictions]
    cost_missing = sum(1 for cost in costs if cost is None)
    cost_known = bool(costs) and cost_missing == 0
    total_cost = sum(float(cost or 0.0) for cost in costs)
    cost_basis = "provider_reported" if cost_known else "unknown"
    if cost_missing:
        summary_path = run_dir / "summary.json"
        if summary_path.exists():
            try:
                summary_cost = read_json(summary_path).get("score", {}).get("total_cost_usd")
            except (json.JSONDecodeError, OSError):
                summary_cost = None
            if summary_cost is not None:
                total_cost = float(summary_cost)
                cost_known = True
                cost_basis = "provider_reported_partial"
                warnings.append(
                    f"cost excludes {cost_missing} call(s) with no cost record"
                )
    usage_totals: dict[str, int] = defaultdict(int)
    for prediction in valid_predictions + infra_predictions:
        usage = prediction.usage or {}
        usage_totals["input"] += int(usage.get("input") or 0)
        usage_totals["output"] += int(usage.get("output") or 0)
        usage_totals["reasoning"] += int(usage.get("reasoning") or 0)
        usage_totals["total"] += int(usage.get("totalTokens") or 0)

    model = run.get("model", {})
    note = str(
        run.get("aborted_reason")
        or run.get("config", {}).get("notes")
        or ""
    )
    effort = effort_for_run(run)
    tier = tier_for_path(run_dir.relative_to(ROOT) if run_dir.is_relative_to(ROOT) else run_dir)
    route = route_for_run(run)
    status = str(run.get("status") or "unknown")

    all_levels_valid = all(
        level_stats[level]["valid"] >= MIN_VALID_PER_LEVEL for level in levels
    )
    used_levels = [level for level in levels if level_stats[level]["valid"]]
    if len(used_levels) < 2:
        all_levels_valid = False
    score_is_finite = bool(score is not None and score.score is not None and score.censored is None)

    reasons: list[str] = []
    if n_tasks == 0:
        reasons.append("no tasks")
    if n_valid == 0:
        reasons.append("no valid predictions")
    if status != "complete":
        reasons.append(f"run status is {status}")
    if completion < MIN_COMPLETION:
        reasons.append(f"valid completion is {completion:.0%}")
    if not all_levels_valid:
        reasons.append("at least one used level has fewer than 3 valid tasks")
    if score is None:
        reasons.append("frontier is not estimable")
    elif score.censored:
        reasons.append(f"score is censored ({score.censored})")
    elif score.score is None:
        reasons.append("score is not finite")
    if not score_is_finite and not reasons:
        reasons.append("score is not rankable")

    official_ok = (
        tier == "official"
        and status == "complete"
        and n_infra == 0
        and completion == 1.0
        and score_is_finite
        and all_levels_valid
        and effort == "max"
        and route in DIRECT_PROVIDERS
        and tasks_per_level >= 5
    )
    provisional_ok = (
        tier == "provisional"
        and status == "complete"
        and completion >= MIN_COMPLETION
        and score_is_finite
        and all_levels_valid
        and tasks_per_level >= 5
    )
    rankable = official_ok or provisional_ok
    if not rankable and not reasons:
        reasons.append("run does not meet the ranked-row rules")

    row = {
        "run_dir": str(run_dir.relative_to(ROOT)) if run_dir.is_relative_to(ROOT) else str(run_dir),
        "run_id": run.get("run_id"),
        "tier": tier,
        "rankable": rankable,
        "official": official_ok,
        "status": status,
        "model": {
            "key": model.get("key"),
            "name": model.get("name"),
            "lab": model.get("lab"),
            "provider": route,
            "model": model.get("model"),
        },
        "effort": effort,
        "cost_basis": cost_basis,
        "dataset_hash_ok": dataset_hash_ok,
        "levels_tested": levels,
        "tasks_per_level": tasks_per_level,
        "precision_tasks": precision_tasks,
        "precision_levels": [int(level) for level in precision_levels],
        "level_task_counts": manifest.get("level_task_counts"),
        "n_tasks": n_tasks,
        "valid": n_valid,
        "correct": correct,
        "accuracy": (correct / n_valid) if n_valid else None,
        "missing": n_missing,
        "provider_errors": n_infra,
        "completion": completion,
        "cost_usd": total_cost if cost_known else None,
        "cost_known": cost_known,
        "cost_per_100_valid": (total_cost / n_valid * 100) if cost_known and n_valid else None,
        "input_tokens": usage_totals["input"],
        "output_tokens": usage_totals["output"],
        "reasoning_tokens": usage_totals["reasoning"],
        "total_tokens": usage_totals["total"],
        "median_latency_ms": round(statistics.median(latencies)) if latencies else None,
        "p95_latency_ms": percentile(latencies, 0.95),
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
    }
    band_levels: list[int] = []
    band_correct = 0
    band_valid = 0
    if score is not None and score.score is not None:
        low_cut = score.score - 2.0
        high_cut = score.score + 1.0
        for level in levels:
            stats = level_stats[level]
            if low_cut <= level <= high_cut and stats["valid"]:
                band_levels.append(level)
                band_correct += stats["correct"]
                band_valid += stats["valid"]
    band_rate = (band_correct / band_valid) if band_valid else None

    if score is not None:
        row.update(
            {
                "score": score.score if score.censored is None else None,
                "band_levels": band_levels,
                "band_correct": band_correct,
                "band_valid": band_valid,
                "band_rate": band_rate,
                "composite": (
                    score.score * band_rate
                    if score.score is not None and score.censored is None and band_rate is not None
                    else None
                ),
                "size": score.size,
                "score_ci": list(score.ci) if score.ci else None,
                "size_ci": list(score.size_ci) if score.size_ci else None,
                "censored": score.censored,
                "bound": score.bound,
                "bound_size": score.bound_size,
                "scoring_version": score.scoring_version,
            }
        )
    else:
        row.update(
            {
                "score": None,
                "composite": None,
                "band_levels": [],
                "band_correct": 0,
                "band_valid": 0,
                "band_rate": None,
                "size": None,
                "score_ci": None,
                "size_ci": None,
                "censored": None,
                "bound": None,
                "bound_size": None,
                "scoring_version": None,
            }
        )
    return row


def discover_runs(roots: Iterable[Path]) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        found.extend(sorted({path.parent for path in root.rglob("run.json")}))
    return found


def score_label(row: dict[str, Any]) -> str:
    if row.get("score") is not None:
        return f"{row['score']:.2f}"
    if row.get("censored") == "upper":
        return f"≥{row['bound']:.1f}" if row.get("bound") is not None else "≥max"
    if row.get("censored") == "lower":
        return f"<{row['bound']:.1f}" if row.get("bound") is not None else "<min"
    if row.get("censored") == "ambiguous":
        return f"~{row['bound']:.1f}" if row.get("bound") is not None else "ambiguous"
    return "—"


def format_ci(row: dict[str, Any]) -> str:
    ci = row.get("score_ci")
    return f"{ci[0]:.2f}–{ci[1]:.2f}" if ci else "—"


def format_cost(row: dict[str, Any]) -> str:
    if not row.get("cost_known"):
        return "unknown"
    if row.get("cost_usd") is None:
        return "—"
    suffix = "*" if row.get("cost_basis") == "provider_reported_partial" else ""
    return f"${row['cost_usd']:.2f}{suffix}"


def markdown_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| # | Model | Effort | Status | EQB-C | EQB-L (95% CI) | Solved | Band | Cover | Cost | Note |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        name = row.get("model", {}).get("name") or row.get("run_dir")
        receipt = row.get("run_dir") or ""
        linked = f"[{name}]({receipt})" if receipt else name
        composite = (
            f"{row['composite']:.2f}"
            if row.get("composite") is not None and row.get("rankable")
            else "—"
        )
        score = score_label(row)
        if score != "—" and not row.get("rankable") and not row.get("censored"):
            score = f"{score}†"
        ci = row.get("score_ci")
        if ci and row.get("rankable"):
            score = f"{score} ({ci[0]:.2f}–{ci[1]:.2f})"
        band_levels = row.get("band_levels") or []
        band_rate = row.get("band_rate")
        band_label = (
            f"{band_rate * 100:.0f}% (L{band_levels[0]}–L{band_levels[-1]})"
            if band_rate is not None and band_levels
            else "—"
        )
        cover = row.get("coverage")
        note = row.get("short_note") or ""
        status = "Official" if row.get("official") else (
            "Provisional" if row.get("rankable") else "Unranked"
        )
        lines.append(
            "| {rank} | {name} | {effort} | {status} | {composite} | {score} | "
            "{correct}/{n} | {rate} | {cover} | {cost} | {note} |".format(
                rank=row.get("rank") or "—",
                name=linked,
                effort=row.get("effort") or "—",
                status=status,
                composite=composite,
                score=score,
                correct=row.get("correct", 0),
                n=row.get("n_tasks", 0),
                rate=band_label,
                cover=f"{cover * 100:.0f}%" if cover is not None else "—",
                cost=format_cost(row),
                note=note.replace("|", "/"),
            )
        )
    return lines


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    rows = payload["rows"]
    lines = [
        "# EquationBench Linear Leaderboard",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        "Season seed `731992` · ladder v1 · scoring v2. One table, all runs.",
        "",
        "`EQB-C = EQB-L × Band` is the ranked composite. It rewards a high "
        "frontier and reliability near that frontier. `EQB-L` is the 50% "
        "frontier. `Band` is the exact-solve rate over the tested levels in "
        "`[EQB-L - 2, EQB-L + 1]`: the window around the frontier. That window "
        "is fixed in width, so testing extra easy or hard levels does not move "
        "it. `Solved` is exact "
        "answers divided by all tasks. `Cover` is valid tasks divided by all "
        "tasks. Provider errors are excluded from the rate, but they lower the "
        "coverage.",
        "",
    ]
    lines.extend(markdown_table(rows))
    lines += [
        "",
        "## How to read the table",
        "",
        "- Ranked rows are sorted by `EQB-C` (`EQB-L × Band`). `EQB-L` is shown beside it.",
        "- `Band` counts only the tested levels in `[EQB-L - 2, EQB-L + 1]`. Easy levels below the frontier do not inflate it.",
        "- `≥` and `<` are bounds, not finite scores. Those rows are unranked.",
        "- `†` is a finite estimate from a level with fewer than 3 valid tasks. It is shown for reference only and is not ranked.",
        "- `Official` rows use a direct provider and max effort. `Provisional` rows are exploratory.",
        "- Effort levels are not the same test. Use the `Effort` column before you compare rows.",
        "- Official rows use 5 tasks at L1-L8 and 10 tasks at L9-L11.",
        "- DeepSeek high uses 10 tasks at L10-L11. The other high rows use 5 core tasks.",
        "- GPT-6.1 Sol high uses the core 5-task row. Its 10-task precision extension had 7 timeouts and 84% valid completion.",
        "- `*` means the cost excludes at least one timed-out call with no cost record.",
        "",
        "## What the data show",
        "",
        "Astra high and Sol form the top pair. Astra reached L10 5/5 and failed L11 "
        "0/5; Sol passed L10 3/4 and failed L11 0/3. Their band rates are equal "
        "(67%), so EQB-L decides the order: Astra 10.50, Sol 10.33.",
        "",
        "Terra max is third. It is more reliable below L10 (L9 10/10) but weaker at "
        "L10 (6/10), which pulls its band rate to 53%.",
        "",
        "DeepSeek is the least reliable of the four near the frontier. Its L10 rate "
        "is 5/10 at max and 2/10 at high. Its frontier is the same as Terra's, but "
        "its band rate is 9 to 16 points lower.",
        "",
        "L11 (30x30) is still the wall. Astra, Sol, Terra, and DeepSeek all failed "
        "every valid L11 task. No model cleared L11.",
        "",
        "Gemini 4 Argon high reached L9 at 2/4 and then the opencode-go 5-hour limit "
        "blocked L10. It is reported as a bound (>=9.0), not a score.",
        "",
        "## Caveats",
        "",
        "- OpenAI lists `gpt-6.1-sol` and `gpt-6.1-terra`, but no `gpt-6.1-luna`. The Luna row uses `gpt-6-luna`.",
        "- High-effort rows start at L5 (strong models) or L3 (weaker models). The score needs only the levels around the bracket.",
        "- `Band` uses a fixed window around each frontier. A run that stops at a different level can shift the band by a few points, so treat EQB-C differences under 0.5 as noise.",
        "- A degenerate CI (for example 10.50-10.50) means every task at the bracket levels passed or failed. The task bootstrap cannot show variance in that case.",
        "- The stale 2026-10 batch probes are not used in the ranked rows.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fields = [
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
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            model = row.get("model", {})
            ci = row.get("score_ci") or [None, None]
            writer.writerow(
                {
                    "rank": row.get("rank"),
                    "run_dir": row.get("run_dir"),
                    "run_id": row.get("run_id"),
                    "tier": row.get("tier"),
                    "rankable": row.get("rankable"),
                    "official": row.get("official"),
                    "dataset_hash_ok": row.get("dataset_hash_ok"),
                    "status": row.get("status"),
                    "model_key": model.get("key"),
                    "model_name": model.get("name"),
                    "lab": model.get("lab"),
                    "provider": model.get("provider"),
                    "model": model.get("model"),
                    "effort": row.get("effort"),
                    "levels_tested": ",".join(str(level) for level in row.get("levels_tested") or []),
                    "tasks_per_level": row.get("tasks_per_level"),
                    "precision_tasks": row.get("precision_tasks"),
                    "precision_levels": ",".join(
                        str(level) for level in row.get("precision_levels") or []
                    ),
                    "n_tasks": row.get("n_tasks"),
                    "valid": row.get("valid"),
                    "correct": row.get("correct"),
                    "accuracy": row.get("accuracy"),
                    "solved_rate": row.get("solved_rate"),
                    "band_levels": ",".join(
                        str(level) for level in row.get("band_levels") or []
                    ),
                    "band_correct": row.get("band_correct"),
                    "band_valid": row.get("band_valid"),
                    "band_rate": row.get("band_rate"),
                    "coverage": row.get("coverage"),
                    "missing": row.get("missing"),
                    "provider_errors": row.get("provider_errors"),
                    "completion": row.get("completion"),
                    "score": row.get("score"),
                    "composite": row.get("composite"),
                    "score_ci_low": ci[0],
                    "score_ci_high": ci[1],
                    "size": row.get("size"),
                    "censored": row.get("censored"),
                    "bound": row.get("bound"),
                    "cost_usd": row.get("cost_usd"),
                    "cost_known": row.get("cost_known"),
                    "cost_basis": row.get("cost_basis"),
                    "cost_per_100_valid": row.get("cost_per_100_valid"),
                    "input_tokens": row.get("input_tokens"),
                    "output_tokens": row.get("output_tokens"),
                    "reasoning_tokens": row.get("reasoning_tokens"),
                    "total_tokens": row.get("total_tokens"),
                    "median_latency_ms": row.get("median_latency_ms"),
                    "p95_latency_ms": row.get("p95_latency_ms"),
                    "reasons": "; ".join(row.get("reasons") or []),
                    "warnings": "; ".join(row.get("warnings") or []),
                    "note": row.get("note"),
                    "short_note": row.get("short_note"),
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root (default: parent of this script).",
    )
    parser.add_argument(
        "--bootstrap",
        type=int,
        default=2000,
        help="Bootstrap replicates for every re-scored row.",
    )
    parser.add_argument(
        "--include-probes",
        action="store_true",
        help="Also include unranked probe receipts.",
    )
    parser.add_argument("--json-out", type=Path, default=Path("data/leaderboard.json"))
    parser.add_argument("--csv-out", type=Path, default=Path("data/leaderboard.csv"))
    parser.add_argument("--md-out", type=Path, default=Path("docs/leaderboard.md"))
    args = parser.parse_args()

    roots = [args.root / "runs" / "official", args.root / "runs" / "provisional"]
    if args.include_probes:
        roots.append(args.root / "runs" / "probes")

    rows = []
    for run_dir in discover_runs(roots):
        row = load_run(run_dir, args.bootstrap)
        if row is not None:
            rows.append(row)

    # Keep the strongest receipt for a repeated model/effort/route/tier cell.
    def strength(row: dict[str, Any]) -> tuple:
        return (
            1 if row.get("rankable") else 0,
            1 if row.get("score") is not None else 0,
            row.get("n_tasks") or 0,
            row.get("valid") or 0,
            row.get("run_id") or "",
        )

    best: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        model = row.get("model", {})
        key = (
            model.get("key"),
            row.get("effort"),
            model.get("provider"),
        )
        if key not in best or strength(row) > strength(best[key]):
            best[key] = row
    rows = list(best.values())

    ranked = sorted(
        [
            row
            for row in rows
            if row.get("rankable") and row.get("composite") is not None
        ],
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
        key=lambda row: (
            row.get("model", {}).get("name") or "",
            row.get("effort") or "",
        ),
    )
    for row in unranked:
        row["rank"] = None
    ordered = ranked + unranked

    payload = {
        "generated_at": utc_now(),
        "generator": "scripts/build_leaderboard.py",
        "season_seed": 731992,
        "ladder_version": "1",
        "generator_version": "2.0.0",
        "prompt_version": "1.0",
        "scoring_version": "2.0",
        "bootstrap_replicates": args.bootstrap,
        "rules": {
            "min_valid_per_level": MIN_VALID_PER_LEVEL,
            "min_completion": MIN_COMPLETION,
            "ranked_tiers": sorted(RANKED_TIERS),
            "composite": "EQB-C = EQB-L * solve_rate",
            "official_effort": "max",
            "official_providers": sorted(DIRECT_PROVIDERS),
        },
        "ranked_count": len(ranked),
        "unranked_count": len(unranked),
        "rows": ordered,
    }

    json_out = args.root / args.json_out
    csv_out = args.root / args.csv_out
    md_out = args.root / args.md_out
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_csv(ordered, csv_out)
    write_markdown(payload, md_out)

    print(f"Wrote {json_out}")
    print(f"Wrote {csv_out}")
    print(f"Wrote {md_out}")
    print(f"ranked: {len(ranked)}")
    print(f"unranked: {len(unranked)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
