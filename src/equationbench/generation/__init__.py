"""Task generator registry.

EquationBench is intentionally a one-track benchmark: every task is a dense
linear system.  The open-ended ladder in :mod:`equationbench.ladder` is the
primary way to generate tasks; this registry keeps the fixed-set v1 builder
working for the harness tests.
"""

from __future__ import annotations

import random
from typing import Callable

from ..types import GenResult
from . import linear

Generator = Callable[[int, random.Random], GenResult]

GENERATORS: dict[str, Generator] = {
    "linear": linear.generate,
}

FAMILY_DESCRIPTIONS = {
    "linear": (
        "Solve a dense integer linear system with a unique exact integer solution."
    ),
}

LEVEL_SPECS = {
    "linear": linear.LEVEL_SPECS,
}


def generate_for(
    family: str,
    level: int,
    rng: random.Random,
    *,
    n_override: int | None = None,
    coeff_override: int | None = None,
) -> GenResult:
    if family != "linear":
        raise ValueError(f"unknown family {family!r}; only 'linear' is supported")
    if level < 1 or level > 9:
        raise ValueError(f"level must be 1..9, got {level}")
    result = linear.generate(
        level,
        rng,
        n_override=n_override,
        coeff_override=coeff_override,
    )
    if result.answer_type != "integer_list":
        raise ValueError("linear generator returned an invalid answer type")
    return result


__all__ = [
    "FAMILY_DESCRIPTIONS",
    "GENERATORS",
    "LEVEL_SPECS",
    "generate_for",
]
