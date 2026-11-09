"""Run a fixed ladder set and score EQB effective solved levels."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .area import DEFAULT_HORIZON, AreaScore, estimate_area, validate_horizon
from .dataset import DatasetBundle, dataset_hash
from .frontier import LevelResult
from .ladder import (
    COEFF_BOUND,
    DEFAULT_SEASON_SEED,
    MAX_PUBLIC_LEVEL,
    X_BOUND,
    build_level_tasks,
    ladder_manifest,
    ladder_row,
)
from .runner import RunConfig, RunResult, run_benchmark
from .types import (
    Level,
    ModelSpec,
    Prediction,
    Task,
    canonical_json,
    normalize_level,
    sha256_text,
)


def build_ladder_bundle(
    levels: Sequence[float],
    *,
    tasks_per_level: int = 5,
    precision_levels: Sequence[float] | None = None,
    precision_tasks: int = 0,
    season_seed: int | str = DEFAULT_SEASON_SEED,
    coeff_bound: int = COEFF_BOUND,
    x_bound: int = X_BOUND,
) -> DatasetBundle:
    """Build a deterministic fixed ladder task set.

    ``precision_levels`` receive ``precision_tasks`` extra tasks after the
    core bank. Predeclare the allocation for comparable precision estimates.
    """
    selected_levels = sorted({normalize_level(level) for level in levels})
    if not selected_levels:
        raise ValueError("at least one level is required")
    if selected_levels[0] < 1 or selected_levels[-1] > MAX_PUBLIC_LEVEL:
        raise ValueError(f"levels must be in 1..{MAX_PUBLIC_LEVEL}")
    if tasks_per_level < 1:
        raise ValueError("tasks_per_level must be positive")
    if precision_tasks < 0:
        raise ValueError("precision_tasks must be non-negative")
    precision_set = {normalize_level(level) for level in (precision_levels or [])}
    if precision_set and precision_tasks < 1:
        raise ValueError("precision_tasks must be positive when precision_levels are set")
    missing = precision_set - set(selected_levels)
    if missing:
        raise ValueError(f"precision levels are not in the selected levels: {sorted(missing)}")
    if tasks_per_level + precision_tasks > 10:
        raise ValueError("core plus precision tasks must not exceed the 10-task bank")

    tasks: list[Task] = []
    level_task_counts: dict[Level, int] = {}
    for level in selected_levels:
        count = tasks_per_level + (precision_tasks if level in precision_set else 0)
        level_task_counts[level] = count
        tasks.extend(
            build_level_tasks(
                level,
                count,
                season_seed=season_seed,
                coeff_bound=coeff_bound,
                x_bound=x_bound,
            )
        )

    manifest = ladder_manifest(math.ceil(selected_levels[-1]), season_seed=season_seed)
    manifest["levels"] = [ladder_row(level) for level in selected_levels]
    manifest["name"] = f"ladder-L{selected_levels[0]}-L{selected_levels[-1]}"
    precision_note = (
        f"; +{precision_tasks} precision tasks at L{','.join(str(level) for level in sorted(precision_set))}"
        if precision_set
        else ""
    )
    manifest["description"] = (
        f"Fixed paired ladder set: {tasks_per_level} core tasks per level, "
        f"L{selected_levels[0]} to L{selected_levels[-1]}{precision_note}."
    )
    manifest["levels_included"] = selected_levels
    manifest["tasks_per_level"] = tasks_per_level
    manifest["precision_tasks"] = precision_tasks
    manifest["precision_levels"] = sorted(precision_set)
    manifest["level_task_counts"] = {
        str(level): count for level, count in level_task_counts.items()
    }
    manifest["dataset_sha256"] = dataset_hash(tasks)
    manifest["counts"] = {
        "total": len(tasks),
        "by_level": {
            str(level): sum(1 for task in tasks if task.level == level) for level in selected_levels
        },
    }
    manifest["task_hashes"] = {
        task.task_id: sha256_text(
            canonical_json(task.to_dict(include_answer=True, include_solution=True))
        )
        for task in tasks
    }
    return DatasetBundle(path=Path("ladder"), tasks=tasks, manifest=manifest)


def bundle_from_receipt(run: Mapping[str, Any]) -> DatasetBundle | None:
    """Regenerate the task bank a ladder run recorded in its ``run.json``.

    Returns ``None`` for a receipt that does not describe a ladder run.
    """
    manifest = run.get("dataset", {}).get("manifest") or {}
    levels = manifest.get("levels_included")
    if levels is None:
        levels = [row.get("level") for row in manifest.get("levels", [])]
    levels = sorted({normalize_level(level) for level in (levels or []) if level is not None})
    tasks_per_level = int(manifest.get("tasks_per_level") or 0)
    season_seed = manifest.get("season_seed")
    if season_seed is None:
        season_seed = run.get("config", {}).get("season_seed")
    if not levels or tasks_per_level < 1 or season_seed is None:
        return None
    return build_ladder_bundle(
        levels,
        tasks_per_level=tasks_per_level,
        precision_levels=manifest.get("precision_levels") or [],
        precision_tasks=int(manifest.get("precision_tasks") or 0),
        season_seed=season_seed,
    )


def area_from_predictions(
    predictions: Sequence[Prediction],
    tasks: Sequence[Task],
    *,
    bootstrap_replicates: int = 2000,
    bootstrap_seed: int = 1729,
    horizon: int = DEFAULT_HORIZON,
) -> AreaScore:
    """Aggregate valid predictions into per-level counts and estimate EQB."""
    by_task = {prediction.task_id: prediction for prediction in predictions}
    counts: dict[Level, list[int]] = defaultdict(lambda: [0, 0])
    for task in tasks:
        prediction = by_task.get(task.task_id)
        if prediction is None:
            continue
        if prediction.is_infra:
            continue
        counts[task.level][1] += 1
        if prediction.correct:
            counts[task.level][0] += 1

    results = [
        LevelResult.from_counts(level, correct, valid)
        for level, (correct, valid) in sorted(counts.items())
        if valid
    ]
    if not results:
        raise ValueError("no valid predictions to score")
    return estimate_area(
        results,
        horizon=horizon,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
    )


def run_ladder(
    model: ModelSpec,
    levels: Sequence[float],
    *,
    out_dir: Path | None = None,
    tasks_per_level: int = 5,
    precision_levels: Sequence[float] | None = None,
    precision_tasks: int = 0,
    concurrency: int = 2,
    timeout: float | None = 900.0,
    retries: int = 2,
    thinking: str | None = None,
    max_cost: float | None = None,
    force: bool = False,
    notes: str = "",
    season_seed: int | str = DEFAULT_SEASON_SEED,
    bootstrap_replicates: int = 1000,
    horizon: int = DEFAULT_HORIZON,
    on_progress: Callable[[int, int, Prediction], None] | None = None,
) -> tuple[RunResult, AreaScore, DatasetBundle]:
    """Run the fixed ladder and write ``eqb.json`` beside the run receipt."""
    validate_horizon(horizon)
    if bootstrap_replicates < 0:
        raise ValueError("bootstrap_replicates must be non-negative")
    if not any(float(level).is_integer() and 1 <= level <= horizon for level in levels):
        raise ValueError("a scored run needs a whole level within the scoring horizon")
    bundle = build_ladder_bundle(
        levels,
        tasks_per_level=tasks_per_level,
        precision_levels=precision_levels,
        precision_tasks=precision_tasks,
        season_seed=season_seed,
    )
    result = run_benchmark(
        RunConfig(
            model=model,
            dataset=bundle,
            out_dir=out_dir,
            concurrency=concurrency,
            timeout=timeout,
            retries=retries,
            thinking=thinking,
            max_cost=max_cost,
            force=force,
            notes=notes,
            on_progress=on_progress,
        )
    )
    score = area_from_predictions(
        result.predictions,
        bundle.tasks,
        bootstrap_replicates=bootstrap_replicates,
        horizon=horizon,
    )

    valid = sum(1 for prediction in result.predictions if not prediction.is_infra)
    payload = {
        "model": model.to_dict(),
        "levels_tested": list(levels),
        "tasks_per_level": tasks_per_level,
        "precision_levels": sorted({normalize_level(level) for level in (precision_levels or [])}),
        "precision_tasks": precision_tasks,
        "level_task_counts": bundle.manifest.get("level_task_counts"),
        "status": result.status,
        "completion": valid / len(bundle.tasks) if bundle.tasks else 0.0,
        "dataset_sha256": bundle.manifest["dataset_sha256"],
        "ladder_version": bundle.manifest["ladder_version"],
        "season_seed": season_seed if isinstance(season_seed, int) else "<string>",
        "eqb": score.to_dict(),
        "run": result.to_dict(),
    }
    (result.run_dir / "eqb.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    summary_path = result.run_dir / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary.pop("frontier", None)
        summary["eqb"] = score.to_dict()
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return result, score, bundle


__all__ = [
    "build_ladder_bundle",
    "bundle_from_receipt",
    "area_from_predictions",
    "run_ladder",
]
