from __future__ import annotations

from equationbench.scoring import (
    mcnemar_p_value,
    paired_bootstrap,
    score_predictions,
    stratified_bootstrap_indices,
)
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


def test_score_perfect_and_half(tiny_dataset):
    tasks = tiny_dataset.tasks
    perfect = score_predictions(make_preds(tasks), tasks, bootstrap_replicates=100)
    assert perfect.accuracy == 1.0
    assert perfect.score == 100.0
    assert perfect.by_level["5"]["n"] == 1
    half = score_predictions(make_preds(tasks, 2), tasks, bootstrap_replicates=100)
    assert 0 < half.score < 100
    assert half.correct == 3
    assert half.cost_known
    assert half.total_cost_usd is not None


def test_missing_predictions_count_as_incorrect(tiny_dataset):
    tasks = tiny_dataset.tasks
    preds = make_preds(tasks)[:2]
    summary = score_predictions(preds, tasks, bootstrap_replicates=50)
    assert summary.n == 5
    assert summary.missing == 3
    assert summary.correct == 2
    assert summary.completion_rate < 1


def test_bootstrap_is_deterministic(tiny_dataset):
    tasks = tiny_dataset.tasks
    a = stratified_bootstrap_indices(tasks, 20, __import__("random").Random(1))
    b = stratified_bootstrap_indices(tasks, 20, __import__("random").Random(1))
    assert a == b


def test_one_task_per_cell_bootstrap_has_nonzero_width(tiny_dataset):
    tasks = tiny_dataset.tasks  # 35 tasks: one per family/level cell
    perfect = make_preds(tasks, 1)
    mixed = make_preds(tasks, 2)
    summary = score_predictions(mixed, tasks, bootstrap_replicates=300)
    assert summary.score_ci[1] > summary.score_ci[0]
    assert summary.accuracy_ci[1] > summary.accuracy_ci[0]
    paired = paired_bootstrap({"a": perfect, "b": mixed}, tasks, replicates=300)
    assert paired["a"]["score_ci"][1] >= paired["a"]["score_ci"][0]


def test_paired_bootstrap_and_mcnemar(tiny_dataset):
    tasks = tiny_dataset.tasks
    strong = make_preds(tasks, 1)
    weak = make_preds(tasks, 2)
    result = paired_bootstrap({"strong": strong, "weak": weak}, tasks, replicates=200)
    assert result["strong"]["score"] > result["weak"]["score"]
    assert result["strong"]["rank_mean"] < result["weak"]["rank_mean"]
    assert result["strong"]["rank_mean"] < 1.5
    test = mcnemar_p_value(strong, weak, tasks)
    assert test["discordant"] > 0
    assert 0 <= test["p_value"] <= 1
