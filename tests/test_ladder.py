from __future__ import annotations

import itertools
import math

import pytest

from equationbench.ladder import (
    COEFF_BOUND,
    DEFAULT_SEASON_SEED,
    LADDER_GENERATOR_VERSION,
    PRECISION_TASKS,
    TASKS_PER_LEVEL,
    X_BOUND,
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


@pytest.mark.parametrize(
    ("level", "size"),
    [(4.5, 7), (5.5, 9), (6.5, 11), (7.5, 13), (8.5, 17), (9.5, 21), (10.5, 27), (11.5, 34)],
)
def test_half_levels_split_the_real_gap(level, size):
    assert size_for_level(level) == size
    assert size_for_level(math.floor(level)) < size < size_for_level(math.ceil(level))


@pytest.mark.parametrize("level", [1.5, 2.5, 3.5])
def test_half_level_between_adjacent_sizes_does_not_exist(level):
    with pytest.raises(ValueError, match="no system size"):
        size_for_level(level)


def test_only_half_steps_are_levels():
    with pytest.raises(ValueError, match="half steps"):
        size_for_level(9.25)


def test_whole_level_tasks_do_not_depend_on_the_number_type():
    # A level's text is hashed into the seed: "10.0" must never reach it.
    assert build_ladder_task(10.0, 0).task_id == build_ladder_task(10, 0).task_id


def test_half_level_tasks_are_new_and_the_right_size():
    task = build_ladder_task(9.5, 0)
    assert task.metadata["n"] == 21
    assert task.level == 9.5
    assert task.task_id not in {build_ladder_task(level, 0).task_id for level in (9, 10)}
