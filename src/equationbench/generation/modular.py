"""Modular arithmetic with power towers and mixed expressions."""

from __future__ import annotations

import random

from ..mathutil import format_tower_expression, tower_mod
from ..prompts import wrap_task
from ..types import GenResult

LEVEL_SPECS = {
    1: {"modulus": 1_009, "height": 2, "towers": 1, "base_max": 9, "top_max": 9},
    2: {"modulus": 1_000_003, "height": 3, "towers": 1, "base_max": 12, "top_max": 12},
    3: {"modulus": 1_000_003, "height": 3, "towers": 2, "base_max": 15, "top_max": 15},
    4: {"modulus": 1_000_000_007, "height": 4, "towers": 2, "base_max": 20, "top_max": 20},
    5: {"modulus": 1_000_000_007, "height": 5, "towers": 3, "base_max": 32, "top_max": 32},
}


def _combine(terms: list[int], modulus: int) -> int:
    value = terms[0] % modulus
    for i, term in enumerate(terms[1:], start=1):
        if i % 2 == 1:
            value = (value + term) % modulus
        else:
            value = (value * term) % modulus
    return value


def generate(level: int, rng: random.Random) -> GenResult:
    if level not in LEVEL_SPECS:
        raise ValueError(f"unknown modular level: {level}")
    spec = LEVEL_SPECS[level]
    modulus = spec["modulus"]
    towers: list[list[int]] = []
    for _ in range(spec["towers"]):
        tower = [rng.randint(2, spec["base_max"]) for _ in range(spec["height"])]
        tower[-1] = rng.randint(2, spec["top_max"])
        towers.append(tower)

    term_values = [tower_mod(tower, modulus) for tower in towers]
    answer = _combine(term_values, modulus)
    expression = format_tower_expression(towers, modulus)
    body = (
        "Compute the least nonnegative residue of the following expression.\n\n"
        f"E = {expression}\n\n"
        "Here `^` denotes exponentiation and is right-associative, so "
        "`a^(b^(c))` means a raised to the power (b raised to the power c). "
        f"The trailing `mod {modulus}` applies to the entire expression. "
        f"Give the residue as an integer in the interval [0, {modulus - 1}]."
    )
    prompt = wrap_task(body, "integer")
    metadata = {
        "modulus": modulus,
        "height": spec["height"],
        "tower_count": spec["towers"],
        "base_max": spec["base_max"],
        "top_max": spec["top_max"],
        "towers": towers,
        "tower_values": term_values,
        "answer_digits": len(str(answer)),
        "prompt_chars": len(prompt),
    }
    return GenResult(
        prompt=prompt,
        answer=str(answer),
        answer_type="integer",
        solution=(
            "Evaluate each power tower by factoring the modulus into prime powers, "
            "reducing exponents with Euler's theorem, and recombining with CRT."
        ),
        metadata=metadata,
    )
