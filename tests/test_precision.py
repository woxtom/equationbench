"""Tests for bracket-level precision task sets."""

from __future__ import annotations

import pytest

from equationbench.frontier_run import build_ladder_bundle


def test_precision_levels_add_tasks_only_at_the_bracket():
    bundle = build_ladder_bundle(
        [9, 10, 11],
        tasks_per_level=5,
        precision_levels=[10, 11],
        precision_tasks=5,
    )
    counts = {
        level: sum(1 for task in bundle.tasks if task.level == level)
        for level in (9, 10, 11)
    }
    assert counts == {9: 5, 10: 10, 11: 10}
    assert bundle.manifest["level_task_counts"] == {"9": 5, "10": 10, "11": 10}
    assert bundle.manifest["precision_levels"] == [10, 11]
    assert bundle.manifest["precision_tasks"] == 5
    assert len(bundle.tasks) == 25


def test_precision_tasks_are_the_second_half_of_the_bank():
    bundle = build_ladder_bundle(
        [10],
        tasks_per_level=5,
        precision_levels=[10],
        precision_tasks=5,
    )
    indices = sorted(task.metadata["task_index"] for task in bundle.tasks)
    assert indices == list(range(1, 11))


def test_precision_levels_must_be_selected():
    with pytest.raises(ValueError, match="not in the selected levels"):
        build_ladder_bundle([10], precision_levels=[11], precision_tasks=5)


def test_precision_tasks_must_be_positive_with_levels():
    with pytest.raises(ValueError, match="precision_tasks"):
        build_ladder_bundle([10], precision_levels=[10], precision_tasks=0)
