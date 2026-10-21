"""Exact matrix algebra: determinants and determinant of matrix polynomials."""

from __future__ import annotations

import random

from ..mathutil import (
    det_bareiss,
    format_matrix,
    mat_add,
    mat_identity,
    mat_mul,
    mat_scale,
)
from ..prompts import wrap_task
from ..types import GenResult

LEVEL_SPECS = {
    1: {"n": 3, "bound": 3, "mode": "det"},
    2: {"n": 4, "bound": 5, "mode": "det"},
    3: {"n": 5, "bound": 7, "mode": "det"},
    4: {"n": 7, "bound": 9, "mode": "polynomial"},
    5: {"n": 10, "bound": 12, "mode": "polynomial"},
}


def _polynomial_matrix(matrix: list[list[int]], c: int, d: int) -> list[list[int]]:
    n = len(matrix)
    a2 = mat_mul(matrix, matrix)
    result = a2
    if c:
        result = mat_add(result, mat_scale(matrix, c))
    if d:
        result = mat_add(result, mat_scale(mat_identity(n), d))
    return result


def _polynomial_expression(c: int, d: int) -> str:
    expression = "A^2"
    if c:
        expression += f" + {c}A" if c > 0 else f" - {abs(c)}A"
    if d:
        expression += f" + {d}I" if d > 0 else f" - {abs(d)}I"
    return expression


def generate(level: int, rng: random.Random) -> GenResult:
    if level not in LEVEL_SPECS:
        raise ValueError(f"unknown matrix level: {level}")
    spec = LEVEL_SPECS[level]
    n = spec["n"]
    bound = spec["bound"]

    for _attempt in range(200):
        matrix = [
            [rng.randint(-bound, bound) for _ in range(n)] for _ in range(n)
        ]
        if spec["mode"] == "det":
            c = d = None
            target = matrix
            determinant = det_bareiss(target)
        else:
            c = rng.randint(-4, 4)
            d = rng.randint(-4, 4)
            if c == 0 and d == 0:
                c = 1
            target = _polynomial_matrix(matrix, c, d)
            determinant = det_bareiss(target)
        if determinant != 0:
            break
    else:  # pragma: no cover
        raise RuntimeError("could not generate a nonsingular matrix task")

    matrix_text = format_matrix(matrix)
    if spec["mode"] == "det":
        body = (
            "Let\n\n"
            f"A =\n```\n{matrix_text}\n```\n\n"
            "Compute det(A). Give the exact integer."
        )
        expression = "A"
        metadata = {
            "n": n,
            "bound": bound,
            "mode": "det",
            "determinant_digits": len(str(abs(determinant))),
            "matrix_entry_max": max(abs(v) for row in matrix for v in row),
            "prompt_chars": 0,
        }
        solution = "Exact fraction-free elimination gives the determinant."
    else:
        expression = _polynomial_expression(c, d)  # type: ignore[arg-type]
        body = (
            "Let\n\n"
            f"A =\n```\n{matrix_text}\n```\n\n"
            f"and let I be the {n}×{n} identity matrix. Compute\n\n"
            f"det({expression}).\n\n"
            "Here A^2 means the matrix product A·A. Give the exact integer."
        )
        metadata = {
            "n": n,
            "bound": bound,
            "mode": "polynomial",
            "c": c,
            "d": d,
            "determinant_digits": len(str(abs(determinant))),
            "matrix_entry_max": max(abs(v) for row in matrix for v in row),
            "prompt_chars": 0,
        }
        solution = (
            "Form the matrix polynomial, then use exact fraction-free elimination "
            "for its determinant."
        )

    prompt = wrap_task(body, "integer")
    metadata["prompt_chars"] = len(prompt)
    return GenResult(
        prompt=prompt,
        answer=str(determinant),
        answer_type="integer",
        solution=solution,
        metadata=metadata,
    )
