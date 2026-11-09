"""Run summaries: accuracy, usage, cost, and latency for a set of predictions.

The score itself is computed in :mod:`equationbench.area`.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass

from . import SCORING_VERSION
from .stats import percentile
from .types import Prediction, Task


@dataclass
class ScoreSummary:
    n: int
    correct: int
    accuracy: float
    by_level: dict[str, dict[str, float | int]]
    status_counts: dict[str, int]
    missing: int
    completion_rate: float
    total_cost_usd: float | None
    cost_known: bool
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int
    median_latency_ms: int | None
    p95_latency_ms: int | None
    scoring_version: str = SCORING_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def _prediction_cost(prediction: Prediction) -> float | None:
    cost = (prediction.usage or {}).get("cost")
    if isinstance(cost, dict) and cost.get("total") is not None:
        return float(cost["total"])
    return None if prediction.cost_usd is None else float(prediction.cost_usd)


def _usage_total(predictions: Sequence[Prediction], key: str) -> int:
    return sum(int((p.usage or {}).get(key, 0) or 0) for p in predictions)


def _latency(values: Sequence[int], p: float) -> int | None:
    result = percentile(values, p)
    return None if result is None else int(result)


def score_predictions(predictions: Iterable[Prediction], tasks: Sequence[Task]) -> ScoreSummary:
    """Summarize a run.  Missing predictions count as incorrect."""
    by_id = {p.task_id: p for p in predictions}
    matched = [by_id[task.task_id] for task in tasks if task.task_id in by_id]
    missing = len(tasks) - len(matched)
    correct = sum(1 for p in matched if p.correct)
    status_counts = Counter(p.parse_status for p in matched)
    if missing:
        status_counts["missing"] = missing

    by_level: dict[str, dict[str, float | int]] = {}
    for level in sorted({task.level for task in tasks}):
        at_level = [task for task in tasks if task.level == level]
        solved = sum(1 for t in at_level if t.task_id in by_id and by_id[t.task_id].correct)
        by_level[str(level)] = {
            "n": len(at_level),
            "correct": solved,
            "accuracy": solved / len(at_level),
        }

    costs = [cost for p in matched if (cost := _prediction_cost(p)) is not None]
    latencies = [p.latency_ms for p in matched if p.latency_ms > 0]
    return ScoreSummary(
        n=len(tasks),
        correct=correct,
        accuracy=correct / len(tasks) if tasks else 0.0,
        by_level=by_level,
        status_counts=dict(status_counts),
        missing=missing,
        completion_rate=len(matched) / len(tasks) if tasks else 0.0,
        total_cost_usd=sum(costs) if costs else None,
        cost_known=bool(costs),
        input_tokens=_usage_total(matched, "input"),
        output_tokens=_usage_total(matched, "output"),
        reasoning_tokens=_usage_total(matched, "reasoning"),
        total_tokens=_usage_total(matched, "totalTokens"),
        median_latency_ms=_latency(latencies, 0.5),
        p95_latency_ms=_latency(latencies, 0.95),
    )
