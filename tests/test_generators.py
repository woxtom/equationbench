from __future__ import annotations

import random

import pytest

from equationbench import FAMILIES, LEVELS
from equationbench.dataset import DatasetProfile, build_task
from equationbench.generation import GENERATORS, generate_for


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("level", LEVELS)
def test_every_generator_level_produces_a_valid_task(family, level):
    result = generate_for(family, level, random.Random(1000 + level))
    assert result.prompt.strip()
    assert result.answer.strip()
    assert result.answer_type in ("integer", "rational", "integer_list")
    assert "JSON" in result.prompt
    assert result.metadata
    if result.answer_type == "integer":
        int(result.answer)
    elif result.answer_type == "integer_list":
        assert result.answer.startswith("[") and result.answer.endswith("]")


@pytest.mark.parametrize("family", FAMILIES)
def test_generation_is_deterministic(family):
    for level in LEVELS:
        a = generate_for(family, level, random.Random(999 + level))
        b = generate_for(family, level, random.Random(999 + level))
        assert a == b


def test_task_ids_depend_on_seed_and_versions():
    profile = DatasetProfile(name="t", per_cell=1, master_seed=42)
    a = build_task("linear", 1, 0, profile)
    b = build_task("linear", 1, 0, profile)
    c = build_task("linear", 1, 1, profile)
    assert a.task_id == b.task_id
    assert a.task_id != c.task_id
    assert a.answer == b.answer


def test_all_generators_have_level_specs():
    from equationbench.generation import LEVEL_SPECS

    for family in FAMILIES:
        assert set(LEVELS).issubset(set(LEVEL_SPECS[family]))
        assert family in GENERATORS
    assert {6, 7}.issubset(set(LEVEL_SPECS["linear"]))
