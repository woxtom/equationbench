"""Exact scoring, uncertainty intervals, and paired comparisons."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from . import FAMILIES, LEVELS, SCORING_VERSION
from .types import Prediction, Task


@dataclass
class ScoreSummary:
    n: int
    correct: int
    accuracy: float
    weighted_accuracy: float
    score: float
    accuracy_ci: tuple[float, float]
    score_ci: tuple[float, float]
    by_family: dict[str, dict[str, float | int]]
    by_level: dict[str, dict[str, float | int]]
    status_counts: dict[str, int]
    missing: int
    completion_rate: float
    total_cost_usd: float | None
    cost_known: bool
    cost_per_100: float | None
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int
    median_latency_ms: int | None
    p95_latency_ms: int | None
    scoring_version: str = SCORING_VERSION

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "correct": self.correct,
            "accuracy": self.accuracy,
            "weighted_accuracy": self.weighted_accuracy,
            "score": self.score,
            "accuracy_ci": list(self.accuracy_ci),
            "score_ci": list(self.score_ci),
            "by_family": self.by_family,
            "by_level": self.by_level,
            "status_counts": self.status_counts,
            "missing": self.missing,
            "completion_rate": self.completion_rate,
            "total_cost_usd": self.total_cost_usd,
            "cost_known": self.cost_known,
            "cost_per_100": self.cost_per_100,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens,
            "median_latency_ms": self.median_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "scoring_version": self.scoring_version,
        }


def _weighted_accuracy(correctness: Sequence[int], levels: Sequence[int]) -> float:
    total_weight = sum(levels)
    if total_weight == 0:
        return 0.0
    return sum(c * lvl for c, lvl in zip(correctness, levels)) / total_weight


def _percentile(values: Sequence[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * p
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] * (1 - fraction) + ordered[upper] * fraction)


def _strata(tasks: Sequence[Task]) -> dict[tuple[str, int], list[int]]:
    strata: dict[tuple[str, int], list[int]] = defaultdict(list)
    for index, task in enumerate(tasks):
        strata[(task.family, task.level)].append(index)
    return strata


def stratified_bootstrap_indices(
    tasks: Sequence[Task], replicates: int, rng: random.Random
) -> list[list[int]]:
    """Cluster bootstrap over (family, level) cells.

    Resampling tasks *within* a cell is degenerate when a cell contains one
    task (as in the 35-task preview): every replicate would be identical. We
    instead resample cells with replacement and keep every task in each chosen
    cell. This preserves the benchmark's family × level design, produces
    non-zero intervals for one-task-per-cell sets, and still uses the same
    resampled cells for every model in a paired comparison.
    """
    cells = list(_strata(tasks).values())
    if not cells:
        return []
    samples: list[list[int]] = []
    for _ in range(replicates):
        chosen_cells = rng.choices(cells, k=len(cells))
        indices = [index for cell in chosen_cells for index in cell]
        samples.append(indices)
    return samples


def _summarize_usage(predictions: Sequence[Prediction]) -> dict:
    input_tokens = output_tokens = reasoning_tokens = total_tokens = 0
    total_cost = 0.0
    cost_known = False
    for prediction in predictions:
        usage = prediction.usage or {}
        input_tokens += int(usage.get("input", 0) or 0)
        output_tokens += int(usage.get("output", 0) or 0)
        reasoning_tokens += int(usage.get("reasoning", 0) or 0)
        total_tokens += int(usage.get("totalTokens", 0) or 0)
        cost = usage.get("cost")
        if isinstance(cost, dict) and cost.get("total") is not None:
            total_cost += float(cost["total"])
            cost_known = True
        elif prediction.cost_usd is not None:
            total_cost += float(prediction.cost_usd)
            cost_known = True
    latency = sorted(p.latency_ms for p in predictions if p.latency_ms > 0)
    median_latency = int(_percentile(latency, 0.5)) if latency else None
    p95_latency = int(_percentile(latency, 0.95)) if latency else None
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
        "total_cost": total_cost if cost_known else None,
        "cost_known": cost_known,
        "median_latency": median_latency,
        "p95_latency": p95_latency,
    }


def score_predictions(
    predictions: Iterable[Prediction],
    tasks: Sequence[Task],
    *,
    bootstrap_replicates: int = 2000,
    bootstrap_seed: int = 1729,
    missing_as_incorrect: bool = True,
) -> ScoreSummary:
    pred_by_task = {p.task_id: p for p in predictions}
    correctness: list[int] = []
    evaluated_tasks: list[Task] = []
    status_counts: dict[str, int] = defaultdict(int)
    matched: list[Prediction] = []
    missing = 0
    for task in tasks:
        prediction = pred_by_task.get(task.task_id)
        if prediction is None:
            missing += 1
            status_counts["missing"] += 1
            if missing_as_incorrect:
                evaluated_tasks.append(task)
                correctness.append(0)
            continue
        evaluated_tasks.append(task)
        matched.append(prediction)
        status_counts[prediction.parse_status] += 1
        correctness.append(1 if prediction.correct else 0)

    n = len(evaluated_tasks)
    correct = sum(correctness)
    accuracy = correct / n if n else 0.0
    weights = [
        float(task.metadata.get("difficulty", task.level)) for task in evaluated_tasks
    ]
    weighted = _weighted_accuracy(correctness, weights)

    by_family: dict[str, dict[str, float | int]] = {}
    by_level: dict[str, dict[str, float | int]] = {}
    for family in FAMILIES:
        indices = [i for i, task in enumerate(evaluated_tasks) if task.family == family]
        if not indices:
            continue
        family_correct = sum(correctness[i] for i in indices)
        by_family[family] = {
            "n": len(indices),
            "correct": family_correct,
            "accuracy": family_correct / len(indices),
            "score": 100
            * _weighted_accuracy(
                [correctness[i] for i in indices],
                [weights[i] for i in indices],
            ),
        }
    for level in sorted({task.level for task in evaluated_tasks}):
        indices = [i for i, task in enumerate(evaluated_tasks) if task.level == level]
        if not indices:
            continue
        level_correct = sum(correctness[i] for i in indices)
        by_level[str(level)] = {
            "n": len(indices),
            "correct": level_correct,
            "accuracy": level_correct / len(indices),
        }

    rng = random.Random(bootstrap_seed)
    bootstrap_indices = stratified_bootstrap_indices(
        evaluated_tasks, bootstrap_replicates, rng
    ) if evaluated_tasks else []
    accuracy_samples: list[float] = []
    score_samples: list[float] = []
    for indices in bootstrap_indices:
        accuracy_samples.append(sum(correctness[i] for i in indices) / len(indices))
        score_samples.append(
            100
            * _weighted_accuracy(
                [correctness[i] for i in indices],
                [weights[i] for i in indices],
            )
        )

    usage = _summarize_usage(matched)
    n_for_cost = len(matched)
    cost = usage["total_cost"]
    cost_per_100 = (cost / n_for_cost * 100) if cost is not None and n_for_cost else None
    completion = (len(tasks) - missing) / len(tasks) if tasks else 0.0

    return ScoreSummary(
        n=n,
        correct=correct,
        accuracy=accuracy,
        weighted_accuracy=weighted,
        score=100 * weighted,
        accuracy_ci=(
            _percentile(accuracy_samples, 0.025),
            _percentile(accuracy_samples, 0.975),
        ),
        score_ci=(
            _percentile(score_samples, 0.025),
            _percentile(score_samples, 0.975),
        ),
        by_family=by_family,
        by_level=by_level,
        status_counts=dict(status_counts),
        missing=missing,
        completion_rate=completion,
        total_cost_usd=cost,
        cost_known=bool(usage["cost_known"]),
        cost_per_100=cost_per_100,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        reasoning_tokens=usage["reasoning_tokens"],
        total_tokens=usage["total_tokens"],
        median_latency_ms=usage["median_latency"],
        p95_latency_ms=usage["p95_latency"],
        scoring_version=SCORING_VERSION,
    )

def paired_bootstrap(
    predictions_by_model: Mapping[str, Sequence[Prediction]],
    tasks: Sequence[Task],
    *,
    replicates: int = 2000,
    seed: int = 271828,
) -> dict[str, dict]:
    """Bootstrap scores and ranks using the same resampled tasks for every model."""
    task_ids = [task.task_id for task in tasks]
    weights = [float(task.metadata.get("difficulty", task.level)) for task in tasks]
    names = list(predictions_by_model)
    correctness: dict[str, list[int]] = {}
    for name in names:
        by_id = {p.task_id: p for p in predictions_by_model[name]}
        correctness[name] = [
            1 if (p := by_id.get(task_id)) is not None and p.correct else 0
            for task_id in task_ids
        ]
    rng = random.Random(seed)
    samples = stratified_bootstrap_indices(tasks, replicates, rng)
    score_samples: dict[str, list[float]] = {name: [] for name in names}
    rank_samples: dict[str, list[float]] = {name: [] for name in names}
    for indices in samples:
        current = {}
        for name in names:
            current[name] = 100 * _weighted_accuracy(
                [correctness[name][i] for i in indices],
                [weights[i] for i in indices],
            )
        for name in names:
            score_samples[name].append(current[name])
        ordered = sorted(names, key=lambda name: current[name], reverse=True)
        # Average ranks for exact ties.
        i = 0
        while i < len(ordered):
            j = i + 1
            while j < len(ordered) and current[ordered[j]] == current[ordered[i]]:
                j += 1
            average_rank = (i + 1 + j) / 2
            for name in ordered[i:j]:
                rank_samples[name].append(average_rank)
            i = j

    output: dict[str, dict] = {}
    for name in names:
        output[name] = {
            "score": 100
            * _weighted_accuracy(correctness[name], weights),
            "score_ci": [
                _percentile(score_samples[name], 0.025),
                _percentile(score_samples[name], 0.975),
            ],
            "rank_mean": sum(rank_samples[name]) / len(rank_samples[name]),
            "rank_ci": [
                _percentile(rank_samples[name], 0.025),
                _percentile(rank_samples[name], 0.975),
            ],
            "win_probability": sum(1 for r in rank_samples[name] if r == 1)
            / len(rank_samples[name]),
        }
    return output


def mcnemar_p_value(predictions_a: Sequence[Prediction], predictions_b: Sequence[Prediction], tasks: Sequence[Task]) -> dict:
    """Two-sided exact McNemar test on paired per-task outcomes."""
    a = {p.task_id: p.correct for p in predictions_a}
    b = {p.task_id: p.correct for p in predictions_b}
    both_a = both_b = 0
    for task in tasks:
        ca = a.get(task.task_id, False)
        cb = b.get(task.task_id, False)
        if ca and not cb:
            both_a += 1
        elif cb and not ca:
            both_b += 1
    n = both_a + both_b
    if n == 0:
        p_value = 1.0
    elif n <= 1000:
        # Exact two-sided binomial test.
        tail = sum(math.comb(n, k) for k in range(0, min(both_a, both_b) + 1)) / (2**n)
        p_value = min(1.0, 2 * tail)
    else:
        z = (abs(both_a - both_b) - 1) / math.sqrt(n)
        p_value = min(1.0, math.erfc(abs(z) / math.sqrt(2)))
    return {
        "a_only": both_a,
        "b_only": both_b,
        "discordant": n,
        "p_value": p_value,
    }


def pairwise_tests(
    predictions_by_model: Mapping[str, Sequence[Prediction]], tasks: Sequence[Task]
) -> list[dict]:
    names = list(predictions_by_model)
    output = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            result = mcnemar_p_value(predictions_by_model[a], predictions_by_model[b], tasks)
            result["model_a"] = a
            result["model_b"] = b
            output.append(result)
    return output


def task_difficulty(
    predictions_by_model: Mapping[str, Sequence[Prediction]], tasks: Sequence[Task]
) -> dict[str, float]:
    by_task: dict[str, list[bool]] = defaultdict(list)
    for predictions in predictions_by_model.values():
        for prediction in predictions:
            by_task[prediction.task_id].append(prediction.correct)
    return {
        task.task_id: (sum(by_task[task.task_id]) / len(by_task[task.task_id]))
        if by_task[task.task_id]
        else 0.0
        for task in tasks
    }
