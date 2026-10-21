"""Dense linear systems with exact integer solutions."""

from __future__ import annotations

import random

from ..mathutil import det_bareiss, format_integer_list, format_linear_equation
from ..prompts import wrap_task
from ..types import GenResult

LEVEL_SPECS = {
    1: {"n": 3, "coeff_bound": 5, "x_bound": 5},
    2: {"n": 4, "coeff_bound": 9, "x_bound": 7},
    3: {"n": 6, "coeff_bound": 12, "x_bound": 9},
    4: {"n": 9, "coeff_bound": 20, "x_bound": 9},
    5: {"n": 14, "coeff_bound": 30, "x_bound": 9},
    6: {"n": 24, "coeff_bound": 50, "x_bound": 9},
    7: {"n": 30, "coeff_bound": 60, "x_bound": 9},
    8: {"n": 18, "coeff_bound": 36, "x_bound": 9},
    9: {"n": 22, "coeff_bound": 45, "x_bound": 9},
}


def generate_size(
    n: int,
    rng: random.Random,
    *,
    coeff_bound: int = 30,
    x_bound: int = 9,
) -> GenResult:
    """Generate a dense n x n system with a known exact integer solution.

    This is the size-first entry point used by the open-ended ladder.  The
    legacy ``generate(level, ...)`` wrapper below keeps the v1 datasets
    reproducible.
    """
    if n < 2:
        raise ValueError(f"system size must be at least 2, got {n}")
    if coeff_bound < 1:
        raise ValueError(f"coefficient bound must be positive, got {coeff_bound}")
    if x_bound < 1:
        raise ValueError(f"solution bound must be positive, got {x_bound}")

    for _attempt in range(200):
        matrix = [
            [rng.randint(-coeff_bound, coeff_bound) for _ in range(n)]
            for _ in range(n)
        ]
        if any(all(v == 0 for v in row) for row in matrix):
            continue
        if det_bareiss(matrix) == 0:
            continue
        solution = [rng.randint(-x_bound, x_bound) for _ in range(n)]
        if all(v == 0 for v in solution):
            continue
        rhs = [
            sum(matrix[i][j] * solution[j] for j in range(n)) for i in range(n)
        ]
        break
    else:  # pragma: no cover
        raise RuntimeError("could not generate a nonsingular linear system")

    var_names = [f"x{i + 1}" for i in range(n)]
    equations = "\n".join(
        format_linear_equation(matrix[i], rhs[i], var_names) for i in range(n)
    )
    body = (
        "Solve the following system of linear equations exactly over the rationals. "
        "The system has a unique solution.\n\n"
        f"```\n{equations}\n```\n\n"
        f"Give the solution as [x1, x2, ..., x{n}]."
    )
    prompt = wrap_task(body, "integer_list")
    metadata = {
        "n": n,
        "coeff_bound": coeff_bound,
        "x_bound": x_bound,
        "max_rhs_digits": max(len(str(abs(v))) for v in rhs),
        "solution_abs_max": max(abs(v) for v in solution),
        "prompt_chars": len(prompt),
    }
    return GenResult(
        prompt=prompt,
        answer=format_integer_list(solution),
        answer_type="integer_list",
        solution=(
            "The coefficients were constructed from a known integer solution; "
            "fraction-free Gaussian elimination recovers it uniquely."
        ),
        metadata=metadata,
    )


def generate(
    level: int,
    rng: random.Random,
    *,
    n_override: int | None = None,
    coeff_override: int | None = None,
) -> GenResult:
    if level not in LEVEL_SPECS:
        raise ValueError(f"unknown linear level: {level}")
    spec = LEVEL_SPECS[level]
    return generate_size(
        n_override or spec["n"],
        rng,
        coeff_bound=coeff_override or spec["coeff_bound"],
        x_bound=spec["x_bound"],
    )
