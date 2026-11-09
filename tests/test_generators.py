from __future__ import annotations

import random

import pytest

from equationbench.generation.linear import generate_size


@pytest.mark.parametrize("n", [2, 3, 8, 24])
def test_generated_system_is_valid(n):
    result = generate_size(n, random.Random(1000 + n))
    assert result.prompt.strip()
    assert "JSON" in result.prompt
    assert result.answer_type == "integer_list"
    assert result.answer.startswith("[") and result.answer.endswith("]")
    assert result.metadata["n"] == n


def test_generation_is_deterministic():
    assert generate_size(6, random.Random(999)) == generate_size(6, random.Random(999))
    assert generate_size(6, random.Random(999)) != generate_size(6, random.Random(998))
