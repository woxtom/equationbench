from __future__ import annotations

import random
from fractions import Fraction

import sympy as sp

from equationbench.mathutil import (
    det_bareiss,
    format_integer_list,
    format_linear_equation,
    format_rational,
)


def test_determinant_matches_sympy():
    rng = random.Random(7)
    for n in range(1, 9):
        for _ in range(20):
            matrix = [[rng.randint(-9, 9) for _ in range(n)] for _ in range(n)]
            assert det_bareiss(matrix) == int(sp.Matrix(matrix).det())


def test_format_linear_equation():
    assert (
        format_linear_equation([1, -1, 0, 2], 7, ["x1", "x2", "x3", "x4"])
        == "x1 - x2 + 2*x4 = 7"
    )
    assert format_linear_equation([0, 0], 0, ["x1", "x2"]) == "0 = 0"


def test_format_rational_and_integer_list():
    assert format_rational(6) == "6"
    assert format_rational(Fraction(17, 24)) == "17/24"
    assert format_integer_list([3, -1, 7]) == "[3, -1, 7]"
