"""Polynomial expansion: extract one coefficient from a large product."""

from __future__ import annotations

import random

from ..mathutil import format_poly_product, poly_from_factors
from ..prompts import wrap_task
from ..types import GenResult

LEVEL_SPECS = {
    1: {"degree": 5, "coeff_bound": 5},
    2: {"degree": 8, "coeff_bound": 9},
    3: {"degree": 12, "coeff_bound": 15},
    4: {"degree": 20, "coeff_bound": 25},
    5: {"degree": 36, "coeff_bound": 50},
}


def _coefficient_name(k: int, degree: int) -> str:
    if k == 0:
        return "constant term"
    if k == 1:
        return "coefficient of x"
    if k == degree:
        return "leading coefficient"
    return f"coefficient of x^{k}"


def generate(level: int, rng: random.Random) -> GenResult:
    if level not in LEVEL_SPECS:
        raise ValueError(f"unknown polynomial level: {level}")
    spec = LEVEL_SPECS[level]
    degree = spec["degree"]
    bound = spec["coeff_bound"]

    for _attempt in range(100):
        factors = []
        for _ in range(degree):
            a = rng.choice([x for x in range(-bound, bound + 1) if x != 0])
            b = rng.choice([x for x in range(-bound, bound + 1) if x != 0])
            factors.append((a, b))
        coeffs = poly_from_factors(factors)
        nonzero = [i for i, c in enumerate(coeffs) if c != 0]
        k = rng.choice(nonzero)
        answer = coeffs[k]
        if len(str(abs(answer))) <= 600:
            break
    else:  # pragma: no cover
        raise RuntimeError("could not generate a bounded polynomial coefficient")

    product = format_poly_product(factors)
    name = _coefficient_name(k, degree)
    body = (
        "Consider the polynomial\n\n"
        f"P(x) = {product}\n\n"
        f"Compute the {name} in the expansion of P(x)."
    )
    prompt = wrap_task(body, "integer")
    metadata = {
        "degree": degree,
        "coeff_bound": bound,
        "k": k,
        "coefficient_name": name,
        "coefficient_digits": len(str(abs(answer))),
        "answer_sign": "negative" if answer < 0 else "positive",
        "prompt_chars": len(prompt),
    }
    return GenResult(
        prompt=prompt,
        answer=str(answer),
        answer_type="integer",
        solution=(
            f"The coefficient is the k-th elementary symmetric polynomial in the factor "
            f"parameters; exact dynamic programming over the {degree} factors gives "
            f"{len(str(abs(answer)))} digits."
        ),
        metadata=metadata,
    )
