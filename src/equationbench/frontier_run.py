"""Run a fixed ladder set and score the 50% frontier.

This is the bridge between the ladder generator and the provider runner.  It is
deliberately a fixed paired set for now: every model answers the same 5 tasks per
level.  The adaptive staircase can replace it later without changing the score.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Callable, Sequence

from .dataset import DatasetBundle, dataset_hash
from .frontier import FrontierScore, LevelResult, estimate_frontier
from .ladder import (
    DEFAULT_SEASON_SEED,
    MAX_PUBLIC_LEVEL,
    build_level_tasks,
    ladder_manifest,
)
from .runner import RunConfig, RunResult, run_benchmark
from .types import ModelSpec, Prediction, Task, canonical_json, sha256_text


def build_ladder_bundle(
    levels: Sequence[int],
    *,
    tasks_per_level: int = 5,
    season_seed: int | str = DEFAULT_SEASON_SEED,
    coeff_bound: int | None = None,
    x_bound: int | None = None,
) -> DatasetBundle:
    """Build a deterministic fixed ladder task set."""
    selected_levels = sorted(set(int(level) for level in levels))
    if not selected_levels:
        raise ValueError("at least one level is required")
    if selected_levels[0] < 1 or selected_levels[-1] > MAX_PUBLIC_LEVEL:
        raise ValueError(f"levels must be in 1..{MAX_PUBLIC_LEVEL}")
    if tasks_per_level < 1:
        raise ValueError("tasks_per_level must be positive")

    tasks: list[Task] = []
    for level in selected_levels:
        tasks.extend(
            build_level_tasks(
                level,
                tasks_per_level,
                season_seed=season_seed,
                coeff_bound=coeff_bound or 30,
                x_bound=x_bound or 9,
            )
        )

    manifest = ladder_manifest(max(selected_levels), season_seed=season_seed)
    level_set = set(selected_levels)
    manifest["levels"] = [row for row in manifest["levels"] if row["level"] in level_set]
    manifest["name"] = f"ladder-L{selected_levels[0]}-L{selected_levels[-1]}"
    manifest["description"] = (
        f"Fixed paired ladder set: {tasks_per_level} tasks per level, "
        f"L{selected_levels[0]} to L{selected_levels[-1]}."
    )
    manifest["levels_included"] = selected_levels
    manifest["tasks_per_level"] = tasks_per_level
    manifest["dataset_sha256"] = dataset_hash(tasks)
    manifest["counts"] = {
        "total": len(tasks),
        "by_level": {
            str(level): sum(1 for task in tasks if task.level == level)
            for level in selected_levels
        },
    }
    manifest["task_hashes"] = {
        task.task_id: sha256_text(
            canonical_json(
                task.to_dict(include_answer=True, include_solution=True)
            )
        )
        for task in tasks
    }
    return DatasetBundle(path=Path("ladder"), tasks=tasks, manifest=manifest)


def frontier_from_predictions(
    predictions: Sequence[Prediction],
    tasks: Sequence[Task],
    *,
    bootstrap_replicates: int = 2000,
    bootstrap_seed: int = 1729,
) -> FrontierScore:
    """Aggregate predictions into per-level counts and estimate the frontier."""
    by_task = {prediction.task_id: prediction for prediction in predictions}
    counts: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for task in tasks:
        prediction = by_task.get(task.task_id)
        if prediction is None:
            continue
        if prediction.parse_status in ("provider_error", "timeout"):
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
    return estimate_frontier(
        results,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
    )


def run_frontier(
    model: ModelSpec,
    levels: Sequence[int],
    *,
    out_dir: Path | None = None,
    tasks_per_level: int = 5,
    concurrency: int = 2,
    timeout: float | None = 900.0,
    retries: int = 2,
    thinking: str | None = None,
    max_cost: float | None = None,
    force: bool = False,
    notes: str = "",
    season_seed: int | str = DEFAULT_SEASON_SEED,
    bootstrap_replicates: int = 1000,
    on_progress: Callable[[int, int, Prediction], None] | None = None,
) -> tuple[RunResult, FrontierScore, DatasetBundle]:
    """Run the fixed ladder and write ``frontier.json`` beside the run receipt."""
    bundle = build_ladder_bundle(
        levels,
        tasks_per_level=tasks_per_level,
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
    score = frontier_from_predictions(
        result.predictions,
        bundle.tasks,
        bootstrap_replicates=bootstrap_replicates,
    )

    valid = sum(
        1
        for prediction in result.predictions
        if prediction.parse_status not in ("provider_error", "timeout")
    )
    payload = {
        "model": model.to_dict(),
        "levels_tested": list(levels),
        "tasks_per_level": tasks_per_level,
        "status": result.status,
        "completion": valid / len(bundle.tasks) if bundle.tasks else 0.0,
        "dataset_sha256": bundle.manifest["dataset_sha256"],
        "ladder_version": bundle.manifest["ladder_version"],
        "season_seed": season_seed if isinstance(season_seed, int) else "<string>",
        "frontier": score.to_dict(),
        "run": result.to_dict(),
    }
    (result.run_dir / "frontier.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    summary_path = result.run_dir / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["frontier"] = score.to_dict()
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return result, score, bundle


__all__ = [
    "build_ladder_bundle",
    "frontier_from_predictions",
    "run_frontier",
]
