from __future__ import annotations

import math
import random

import sympy as sp

from equationbench.mathutil import (
    carmichael_lambda,
    det_bareiss,
    format_rational,
    poly_derivative,
    poly_eval,
    poly_from_factors,
    poly_integral_definite,
    recurrence_term,
    tower_mod,
    tower_value_capped,
)


def test_determinant_matches_sympy():
    rng = random.Random(7)
    for n in range(1, 9):
        for _ in range(20):
            matrix = [[rng.randint(-9, 9) for _ in range(n)] for _ in range(n)]
            assert det_bareiss(matrix) == int(sp.Matrix(matrix).det())


def test_polynomial_expansion_and_derivative():
    factors = [(2, 3), (-1, 5), (4, -2)]
    coeffs = poly_from_factors(factors)
    for x in (-3, 0, 2, 7):
        expected = (2 * x + 3) * (-x + 5) * (4 * x - 2)
        assert poly_eval(coeffs, x) == expected
    derivative = poly_derivative(coeffs, 1)
    assert poly_eval(derivative, 7) == sp.diff(
        (2 * sp.Symbol("x") + 3) * (-sp.Symbol("x") + 5) * (4 * sp.Symbol("x") - 2),
        sp.Symbol("x"),
    ).subs(sp.Symbol("x"), 7)
    assert format_rational(poly_integral_definite([1, 2, 3], 0, 1)) == "3"


def test_recurrence_matches_direct_iteration():
    rng = random.Random(11)
    for k in range(1, 6):
        for _ in range(30):
            coeffs = [rng.randint(-5, 5) for _ in range(k)]
            if coeffs[-1] == 0:
                coeffs[-1] = 1
            initial = [rng.randint(-9, 9) for _ in range(k)]
            mod = rng.choice([1009, 1000003, 1000000007, None])
            seq = [value % mod if mod else value for value in initial]
            for i in range(k, 60):
                value = sum(coeffs[j] * seq[i - 1 - j] for j in range(k))
                seq.append(value % mod if mod else value)
            for n in (0, 1, k - 1, k, 20, 59):
                assert recurrence_term(coeffs, initial, n, mod) == seq[n]


def test_carmichael_lambda():
    assert carmichael_lambda(1) == 1
    assert carmichael_lambda(8) == 2
    assert carmichael_lambda(1009) == 1008
    for n in range(2, 200):
        lam = carmichael_lambda(n)
        for a in range(2, min(n, 20)):
            if math.gcd(a, n) == 1:
                assert pow(a, lam, n) == 1


def test_tower_mod_against_direct_when_feasible():
    rng = random.Random(13)
    for mod in (2, 4, 8, 9, 16, 27, 1009, 1000003):
        for _ in range(100):
            height = rng.randint(1, 3)
            bases = [rng.randint(2, 9) for _ in range(height)]
            try:
                value = bases[-1]
                for base in reversed(bases[:-1]):
                    if value > 10000:
                        raise OverflowError
                    value = base**value
            except (OverflowError, MemoryError):
                continue
            assert tower_mod(bases, mod) == value % mod


def test_tower_mod_prime_reduction():
    rng = random.Random(17)
    for mod in (1009, 1000003, 1000000007):
        for _ in range(50):
            height = rng.randint(2, 6)
            bases = [rng.randint(2, 30) for _ in range(height)]
            if bases[0] % mod == 0:
                expected = 0
            else:
                exponent = tower_mod(bases[1:], mod - 1)
                expected = pow(bases[0], exponent, mod)
            assert tower_mod(bases, mod) == expected


def test_tower_capped():
    value, large = tower_value_capped([9, 11, 5], 1000)
    assert large and value == 1000
    value, large = tower_value_capped([2, 3], 1000)
    assert value == 8 and not large
