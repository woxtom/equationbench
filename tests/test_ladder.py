from __future__ import annotations

import itertools

import pytest

from equationbench.ladder import (
    COEFF_BOUND,
    DEFAULT_SEASON_SEED,
    LADDER_GENERATOR_VERSION,
    PRECISION_TASKS,
    TASKS_PER_LEVEL,
    X_BOUND,
    build_bank,
    build_ladder_task,
    build_level_tasks,
    estimate_prompt_chars,
    estimate_prompt_tokens,
    ideal_size_for_level,
    ladder_manifest,
    ladder_rows,
    level_for_size,
    size_for_level,
)


def test_ladder_sizes_are_geometric_and_monotonic():
    sizes = [size_for_level(level) for level in range(1, 21)]
    assert sizes[:5] == [3, 4, 5, 6, 8]
    assert sizes[9] == 24
    assert sizes[12] == 48
    assert sizes[15] == 96
    assert sizes[18] == 192
    assert sizes[19] == 242
    assert all(right > left for left, right in itertools.pairwise(sizes))


def test_level_for_size_is_inverse_at_exact_doublings():
    for level in (1, 4, 7, 10, 13, 16, 19):
        size = size_for_level(level)
        assert level_for_size(size) == pytest.approx(level, abs=0.02)
        assert ideal_size_for_level(level) == pytest.approx(size, abs=0.51)


def test_ladder_rejects_bad_levels():
    with pytest.raises(ValueError):
        size_for_level(0)
    with pytest.raises(ValueError):
        level_for_size(0)
    with pytest.raises(ValueError):
        build_ladder_task(1, -1)


def test_ladder_task_is_deterministic_and_correctly_sized():
    first = build_ladder_task(10, 0)
    second = build_ladder_task(10, 0)
    assert first.task_id == second.task_id
    assert first.answer == second.answer
    assert first.level == 10
    assert first.metadata["n"] == size_for_level(10) == 24
    assert first.metadata["ladder_level"] == 10
    assert first.metadata["task_index"] == 1
    assert first.answer_type == "integer_list"
    assert first.answer.startswith("[") and first.answer.endswith("]")
    assert first.generator_version == LADDER_GENERATOR_VERSION
    assert first.metadata["coeff_bound"] == COEFF_BOUND
    assert first.metadata["x_bound"] == X_BOUND


def test_level_tasks_are_distinct_and_share_the_level():
    tasks = build_level_tasks(5, TASKS_PER_LEVEL)
    assert len(tasks) == TASKS_PER_LEVEL
    assert len({task.task_id for task in tasks}) == TASKS_PER_LEVEL
    assert all(task.level == 5 for task in tasks)
    assert all(task.metadata["n"] == size_for_level(5) for task in tasks)


def test_build_bank_contains_core_and_precision_tasks():
    tasks = build_bank([1, 2], tasks_per_level=2, precision_tasks=1)
    assert len(tasks) == 6
    assert {task.level for task in tasks} == {1, 2}
    level_one = [task for task in tasks if task.level == 1]
    assert len(level_one) == 3
    assert max(task.metadata["task_index"] for task in level_one) == 3


def test_prompt_estimates_are_monotonic():
    rows = ladder_rows(20)
    assert [row["level"] for row in rows] == list(range(1, 21))
    estimates = [row["approx_prompt_tokens"] for row in rows]
    assert all(right > left for left, right in itertools.pairwise(estimates))
    assert estimate_prompt_tokens(24) > 1000
    assert estimate_prompt_chars(24) > estimate_prompt_chars(8)


def test_ladder_manifest_describes_the_public_protocol():
    manifest = ladder_manifest(20)
    assert manifest["ladder_version"] == "1"
    assert manifest["coefficient_bound"] == COEFF_BOUND
    assert manifest["solution_bound"] == X_BOUND
    assert manifest["tasks_per_level"] == TASKS_PER_LEVEL
    assert manifest["precision_tasks"] == PRECISION_TASKS
    assert manifest["official_cap_level"] == 17
    assert manifest["season_seed"] == DEFAULT_SEASON_SEED
    assert len(manifest["levels"]) == 20
    assert manifest["levels"][9]["size"] == 24
