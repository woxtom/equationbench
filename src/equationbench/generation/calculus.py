"""Calculus on large factored polynomials: high derivatives and definite integrals."""

from __future__ import annotations

import random

from ..mathutil import (
    format_poly_product,
    format_rational,
    poly_derivative,
    poly_eval,
    poly_from_factors,
    poly_integral_definite,
)
from ..prompts import wrap_task
from ..types import GenResult

LEVEL_SPECS = {
    1: {"degree": 4, "coeff_bound": 5, "mode": "derivative", "order": 1},
    2: {"degree": 6, "coeff_bound": 9, "mode": "derivative", "order": 1},
    3: {"degree": 9, "coeff_bound": 12, "mode": "derivative", "order": 2},
    4: {"degree": 14, "coeff_bound": 20, "mode": "integral"},
    5: {"degree": 22, "coeff_bound": 30, "mode": "integral"},
}


def generate(level: int, rng: random.Random) -> GenResult:
    if level not in LEVEL_SPECS:
        raise ValueError(f"unknown calculus level: {level}")
    spec = LEVEL_SPECS[level]
    degree = spec["degree"]
    bound = spec["coeff_bound"]
    factors = []
    for _ in range(degree):
        a = rng.choice([x for x in range(-bound, bound + 1) if x != 0])
        b = rng.randint(-bound, bound)
        factors.append((a, b))
    coeffs = poly_from_factors(factors)
    product = format_poly_product(factors)

    if spec["mode"] == "derivative":
        order = spec["order"]
        x0 = rng.randint(-4, 4)
        derivative = poly_derivative(coeffs, order)
        value = poly_eval(derivative, x0)
        answer = format_rational(value)
        ordinal = "first" if order == 1 else "second"
        body = (
            f"Let\n\nf(x) = {product}.\n\n"
            f"Compute the {ordinal} derivative of f at x = {x0}. "
            "Give the exact value."
        )
        metadata = {
            "degree": degree,
            "coeff_bound": bound,
            "mode": "derivative",
            "order": order,
            "x0": x0,
            "answer_digits": len(str(abs(int(value)))),
            "prompt_chars": 0,
        }
        solution = (
            f"Expand f, differentiate {order} time(s), and evaluate at x={x0} using "
            "exact integer arithmetic."
        )
    else:
        lower = rng.randint(-2, 1)
        upper = rng.randint(lower + 1, 2)
        value = poly_integral_definite(coeffs, lower, upper)
        answer = format_rational(value)
        body = (
            f"Let\n\nf(x) = {product}.\n\n"
            f"Compute the exact value of the definite integral "
            f"∫_{{{lower}}}^{{{upper}}} f(x) dx."
        )
        metadata = {
            "degree": degree,
            "coeff_bound": bound,
            "mode": "integral",
            "lower": lower,
            "upper": upper,
            "answer_digits": len(str(abs(value.numerator))) + len(str(value.denominator)),
            "prompt_chars": 0,
        }
        solution = (
            "Expand f, integrate termwise, and evaluate the antiderivative at the "
            "two limits using exact rational arithmetic."
        )

    prompt = wrap_task(body, "rational")
    metadata["prompt_chars"] = len(prompt)
    return GenResult(
        prompt=prompt,
        answer=answer,
        answer_type="rational",
        solution=solution,
        metadata=metadata,
    )
