"""Exact arithmetic and formatting helpers for linear systems.

Nothing here uses floating point.  Ground truth is constructed with Python
integers, which is what makes the benchmark exactly scorable.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Sequence


def format_rational(value: Fraction | int) -> str:
    f = Fraction(value)
    if f.denominator == 1:
        return str(f.numerator)
    return f"{f.numerator}/{f.denominator}"


def det_bareiss(matrix: Sequence[Sequence[int]]) -> int:
    """Exact integer determinant using the fraction-free Bareiss algorithm."""
    n = len(matrix)
    if n == 0:
        return 1
    if any(len(row) != n for row in matrix):
        raise ValueError("determinant requires a square matrix")
    a = [list(row) for row in matrix]
    sign = 1
    prev = 1
    for k in range(n - 1):
        if a[k][k] == 0:
            swap = next((r for r in range(k + 1, n) if a[r][k] != 0), None)
            if swap is None:
                return 0
            a[k], a[swap] = a[swap], a[k]
            sign = -sign
        pivot = a[k][k]
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                a[i][j] = (a[i][j] * pivot - a[i][k] * a[k][j]) // prev
        prev = pivot
        # The entries below the pivot are mathematically zero after the update.
        for i in range(k + 1, n):
            a[i][k] = 0
    return sign * a[n - 1][n - 1]


def _format_linear_term(coef: int, var: str, first: bool) -> str:
    if coef == 0:
        return ""
    sign = "-" if coef < 0 else "+"
    magnitude = abs(coef)
    body = var if magnitude == 1 else f"{magnitude}*{var}"
    if first:
        return body if sign == "+" else f"-{body}"
    return f" {sign} {body}"


def format_linear_equation(coeffs: Sequence[int], rhs: int, var_names: Sequence[str]) -> str:
    terms = []
    first = True
    for coef, var in zip(coeffs, var_names):
        text = _format_linear_term(coef, var, first)
        if text:
            terms.append(text)
            first = False
    lhs = "".join(terms) if terms else "0"
    return f"{lhs} = {rhs}"


def format_integer_list(values: Sequence[int]) -> str:
    return "[" + ", ".join(str(v) for v in values) + "]"
