from __future__ import annotations

from equationbench.scoring import score_predictions
from equationbench.types import Prediction


def make_preds(tasks, correct_every=1):
    return [
        Prediction(
            task_id=task.task_id,
            model_key="fake",
            raw_response="",
            parsed_answer=task.answer if (i % correct_every == 0) else "0",
            correct=(i % correct_every == 0),
            parse_status="correct" if (i % correct_every == 0) else "wrong",
            latency_ms=100 + i,
            usage={"input": 10, "output": 5, "totalTokens": 15, "cost": {"total": 0.001}},
        )
        for i, task in enumerate(tasks)
    ]


def test_summary_counts_correct_answers_and_usage(tiny_dataset):
    tasks = tiny_dataset.tasks
    summary = score_predictions(make_preds(tasks, 2), tasks)
    assert summary.n == 5
    assert summary.correct == 3
    assert summary.accuracy == 0.6
    assert summary.total_tokens == 75
    assert summary.total_cost_usd == 0.005
    assert summary.cost_known
    assert summary.by_level["1"] == {"n": 1, "correct": 1, "accuracy": 1.0}
    assert summary.median_latency_ms == 102


def test_missing_predictions_count_as_incorrect(tiny_dataset):
    tasks = tiny_dataset.tasks
    summary = score_predictions(make_preds(tasks[:3]), tasks)
    assert summary.correct == 3
    assert summary.missing == 2
    assert summary.status_counts["missing"] == 2
    assert summary.accuracy == 0.6
    assert summary.completion_rate == 0.6


def test_unknown_cost_stays_unknown(tiny_dataset):
    tasks = tiny_dataset.tasks
    predictions = [
        Prediction(task_id=t.task_id, model_key="m", raw_response="", parsed_answer=None,
                   correct=False, parse_status="wrong")
        for t in tasks
    ]
    summary = score_predictions(predictions, tasks)
    assert summary.total_cost_usd is None
    assert not summary.cost_known
