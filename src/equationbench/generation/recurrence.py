"""Large-index linear recurrences evaluated modulo a prime."""

from __future__ import annotations

import random

from ..mathutil import recurrence_term
from ..prompts import wrap_task
from ..types import GenResult

LEVEL_SPECS = {
    1: {"order": 2, "n_min": 5, "n_max": 20, "modulus": 1_009, "coeff_bound": 5},
    2: {"order": 2, "n_min": 100, "n_max": 1_000, "modulus": 1_000_003, "coeff_bound": 9},
    3: {"order": 3, "n_min": 1_000_000, "n_max": 10_000_000, "modulus": 1_000_000_007, "coeff_bound": 9},
    4: {"order": 4, "n_min": 10**12, "n_max": 10**13, "modulus": 998_244_353, "coeff_bound": 12},
    5: {"order": 5, "n_min": 10**18, "n_max": 9 * 10**18, "modulus": 1_000_000_007, "coeff_bound": 15},
}


def _recurrence_expression(coeffs: list[int], order: int) -> str:
    parts: list[str] = []
    for i, coefficient in enumerate(coeffs, start=1):
        if coefficient == 0:
            continue
        term = f"a_(n-{i})"
        if coefficient == 1:
            body = term
        elif coefficient == -1:
            body = f"-{term}"
        else:
            body = f"{coefficient}*{term}"
        if not parts:
            parts.append(body)
        elif body.startswith("-"):
            parts.append(f" - {body[1:]}")
        else:
            parts.append(f" + {body}")
    return "".join(parts)


def generate(level: int, rng: random.Random) -> GenResult:
    if level not in LEVEL_SPECS:
        raise ValueError(f"unknown recurrence level: {level}")
    spec = LEVEL_SPECS[level]
    order = spec["order"]
    coeff_bound = spec["coeff_bound"]
    modulus = spec["modulus"]
    coeffs = [rng.randint(-coeff_bound, coeff_bound) for _ in range(order)]
    if coeffs[-1] == 0:
        coeffs[-1] = rng.choice([-1, 1]) * rng.randint(1, coeff_bound)
    initial = [rng.randint(-9, 9) for _ in range(order)]
    n = rng.randint(spec["n_min"], spec["n_max"])
    answer = recurrence_term(coeffs, initial, n, modulus)

    initial_text = ", ".join(
        f"a_{i} = {value}" for i, value in enumerate(initial)
    )
    recurrence_text = _recurrence_expression(coeffs, order)
    body = (
        "A sequence is defined by\n\n"
        f"{initial_text}\n\n"
        f"and, for n ≥ {order},\n\n"
        f"a_n = {recurrence_text}.\n\n"
        f"Compute a_{n} mod {modulus}. Give the least nonnegative residue."
    )
    prompt = wrap_task(body, "integer")
    metadata = {
        "order": order,
        "n": n,
        "n_digits": len(str(n)),
        "modulus": modulus,
        "coeff_bound": coeff_bound,
        "coefficients": coeffs,
        "initial": initial,
        "answer_digits": len(str(answer)),
        "prompt_chars": len(prompt),
    }
    return GenResult(
        prompt=prompt,
        answer=str(answer),
        answer_type="integer",
        solution=(
            f"Binary exponentiation of the {order}×{order} companion matrix, or "
            "Kitamasa polynomial exponentiation, gives the residue."
        ),
        metadata=metadata,
    )
