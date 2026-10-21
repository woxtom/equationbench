"""Task generator registry.

Each family is a pure function of (level, random.Random). The dataset builder
derives the RNG from a master seed, so the same family/level/index always
produces the same task.
"""

from __future__ import annotations

import random
from typing import Callable

from .. import FAMILIES
from ..types import GenResult
from . import arith, calculus, linear, matrix, modular, poly, recurrence

Generator = Callable[[int, random.Random], GenResult]

GENERATORS: dict[str, Generator] = {
    "arith": arith.generate,
    "poly": poly.generate,
    "linear": linear.generate,
    "calculus": calculus.generate,
    "modular": modular.generate,
    "matrix": matrix.generate,
    "recurrence": recurrence.generate,
}

FAMILY_DESCRIPTIONS = {
    "arith": (
        "Deep, fully parenthesized integer expressions with addition, subtraction, "
        "multiplication, exponentiation, and factorials."
    ),
    "poly": (
        "Expand a product of many linear factors and extract one exact coefficient."
    ),
    "linear": (
        "Solve a dense integer linear system with a unique exact integer solution."
    ),
    "calculus": (
        "Differentiate a large factored polynomial at a point, or integrate it over "
        "an interval exactly."
    ),
    "modular": (
        "Evaluate mixed expressions containing right-associative power towers modulo "
        "a large prime."
    ),
    "matrix": (
        "Compute an exact determinant, sometimes of a matrix polynomial such as "
        "A^2 - 2A + 3I."
    ),
    "recurrence": (
        "Evaluate a high-order linear recurrence at an enormous index modulo a prime."
    ),
}

LEVEL_SPECS = {
    "arith": arith.LEVEL_SPECS,
    "poly": poly.LEVEL_SPECS,
    "linear": linear.LEVEL_SPECS,
    "calculus": calculus.LEVEL_SPECS,
    "modular": modular.LEVEL_SPECS,
    "matrix": matrix.LEVEL_SPECS,
    "recurrence": recurrence.LEVEL_SPECS,
}


def generate_for(
    family: str,
    level: int,
    rng: random.Random,
    *,
    n_override: int | None = None,
    coeff_override: int | None = None,
) -> GenResult:
    if family not in GENERATORS:
        raise ValueError(f"unknown family {family!r}; choose from {FAMILIES}")
    if level < 1 or level > 9:
        raise ValueError(f"level must be 1..9, got {level}")
    if family == "linear":
        result = linear.generate(
            level,
            rng,
            n_override=n_override,
            coeff_override=coeff_override,
        )
    else:
        result = GENERATORS[family](level, rng)
    if result.answer_type not in ("integer", "rational", "integer_list"):
        raise ValueError(f"generator {family} returned invalid answer type")
    return result


__all__ = [
    "GENERATORS",
    "FAMILY_DESCRIPTIONS",
    "LEVEL_SPECS",
    "generate_for",
]
