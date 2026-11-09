"""Dense linear systems with exact integer solutions."""

from __future__ import annotations

import random

from ..mathutil import det_bareiss, format_integer_list, format_linear_equation
from ..prompts import wrap_task
from ..types import GenResult


def generate_size(
    n: int,
    rng: random.Random,
    *,
    coeff_bound: int = 30,
    x_bound: int = 9,
) -> GenResult:
    """Generate a dense n x n system with a known exact integer solution.

    The ladder decides the size; this only builds the system.
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
