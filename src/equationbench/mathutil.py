"""Exact arithmetic helpers shared by task generators and verifiers.

Nothing in this module uses floating point. Every generator's ground truth is
computed with integer / rational arithmetic, which is what makes the benchmark
exactly scorable.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Iterable, Sequence

# ---------------------------------------------------------------------------
# Polynomials. Coefficients are stored in ascending order: [c0, c1, ...].
# ---------------------------------------------------------------------------


def poly_mul(a: Sequence[int], b: Sequence[int]) -> list[int]:
    if not a or not b:
        return []
    out = [0] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        if ai == 0:
            continue
        for j, bj in enumerate(b):
            out[i + j] += ai * bj
    return out


def poly_from_factors(factors: Iterable[tuple[int, int]]) -> list[int]:
    """Expand prod(a_i*x + b_i) into ascending coefficients."""
    coeffs = [1]
    for a, b in factors:
        coeffs = poly_mul(coeffs, [b, a])
    return coeffs


def poly_eval(coeffs: Sequence[int], x: int | Fraction) -> int | Fraction:
    result: int | Fraction = 0
    for c in reversed(coeffs):
        result = result * x + c
    return result


def poly_derivative(coeffs: Sequence[int], order: int = 1) -> list[int]:
    out = list(coeffs)
    for _ in range(order):
        if len(out) <= 1:
            return [0]
        out = [i * out[i] for i in range(1, len(out))]
    return out


def poly_integral_definite(
    coeffs: Sequence[int], lower: int | Fraction, upper: int | Fraction
) -> Fraction:
    """Exact integral of a polynomial over [lower, upper]."""
    lo = Fraction(lower)
    hi = Fraction(upper)
    total = Fraction(0)
    for i, c in enumerate(coeffs):
        if c == 0:
            continue
        power = i + 1
        total += Fraction(c, power) * (hi**power - lo**power)
    return total


def format_rational(value: Fraction | int) -> str:
    f = Fraction(value)
    if f.denominator == 1:
        return str(f.numerator)
    return f"{f.numerator}/{f.denominator}"


def format_binomial_factor(a: int, b: int, var: str = "x") -> str:
    if a == 0:
        body = str(b)
    elif a == 1:
        body = var
    elif a == -1:
        body = f"-{var}"
    else:
        body = f"{a}{var}"
    if b == 0:
        return f"({body})"
    if b > 0:
        return f"({body} + {b})"
    return f"({body} - {abs(b)})"


def format_poly_product(factors: Sequence[tuple[int, int]], var: str = "x") -> str:
    return "".join(format_binomial_factor(a, b, var) for a, b in factors)


# ---------------------------------------------------------------------------
# Matrices and determinants.
# ---------------------------------------------------------------------------


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


def mat_mul(
    a: Sequence[Sequence[int]], b: Sequence[Sequence[int]], mod: int | None = None
) -> list[list[int]]:
    n = len(a)
    m = len(b[0])
    inner = len(b)
    out = [[0] * m for _ in range(n)]
    for i in range(n):
        for k in range(inner):
            aik = a[i][k]
            if aik == 0:
                continue
            for j in range(m):
                out[i][j] += aik * b[k][j]
        if mod is not None:
            for j in range(m):
                out[i][j] %= mod
    return out


def mat_identity(n: int) -> list[list[int]]:
    return [[1 if i == j else 0 for j in range(n)] for i in range(n)]


def mat_add(a: Sequence[Sequence[int]], b: Sequence[Sequence[int]]) -> list[list[int]]:
    return [[x + y for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def mat_scale(a: Sequence[Sequence[int]], s: int) -> list[list[int]]:
    return [[s * x for x in row] for row in a]


def mat_pow(a: Sequence[Sequence[int]], exponent: int, mod: int | None = None) -> list[list[int]]:
    if exponent < 0:
        raise ValueError("negative matrix exponent")
    n = len(a)
    result = mat_identity(n)
    base = [list(row) for row in a]
    if mod is not None:
        base = [[x % mod for x in row] for row in base]
    while exponent:
        if exponent & 1:
            result = mat_mul(result, base, mod)
        exponent >>= 1
        if exponent:
            base = mat_mul(base, base, mod)
    return result


def mat_vec_mul(
    a: Sequence[Sequence[int]], v: Sequence[int], mod: int | None = None
) -> list[int]:
    out = []
    for row in a:
        value = sum(x * y for x, y in zip(row, v))
        out.append(value % mod if mod is not None else value)
    return out


def format_matrix(matrix: Sequence[Sequence[int]]) -> str:
    if not matrix:
        return "[]"
    width = max(len(str(x)) for row in matrix for x in row)
    lines = []
    for row in matrix:
        cells = " ".join(f"{x:>{width}}" for x in row)
        lines.append(f"[ {cells} ]")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Recurrences.
# ---------------------------------------------------------------------------


def recurrence_term(
    coeffs: Sequence[int],
    initial: Sequence[int],
    n: int,
    mod: int | None = None,
) -> int:
    """a_n for a_n = c1*a_{n-1} + ... + ck*a_{n-k}.

    ``coeffs`` is [c1, ..., ck]; ``initial`` is [a_0, ..., a_{k-1}].
    O(k^3 log n) via the companion matrix. Exact when mod is None.
    """
    k = len(coeffs)
    if k == 0:
        raise ValueError("recurrence needs at least one coefficient")
    if len(initial) < k:
        raise ValueError("initial state is shorter than recurrence order")
    if n < 0:
        raise ValueError("negative recurrence index")
    if n < k:
        value = initial[n]
        return value % mod if mod is not None else value
    companion = [[0] * k for _ in range(k)]
    companion[0] = list(coeffs)
    for i in range(1, k):
        companion[i][i - 1] = 1
    power = mat_pow(companion, n - (k - 1), mod)
    state = list(reversed(initial[:k]))  # [a_{k-1}, ..., a_0]
    out = mat_vec_mul(power, state, mod)
    return out[0]


# ---------------------------------------------------------------------------
# Modular arithmetic, Carmichael's lambda, and power towers.
# ---------------------------------------------------------------------------


def factorize(n: int) -> dict[int, int]:
    if n < 1:
        raise ValueError("factorization requires a positive integer")
    factors: dict[int, int] = {}
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors[d] = factors.get(d, 0) + 1
            n //= d
        d = 3 if d == 2 else d + 2
    if n > 1:
        factors[n] = factors.get(n, 0) + 1
    return factors


def carmichael_lambda(n: int) -> int:
    """Carmichael's totient function lambda(n)."""
    if n < 1:
        raise ValueError("lambda requires a positive integer")
    if n == 1:
        return 1
    result = 1
    for p, e in factorize(n).items():
        if p == 2:
            if e == 1:
                component = 1
            elif e == 2:
                component = 2
            else:
                component = 1 << (e - 2)
        else:
            component = (p - 1) * (p ** (e - 1))
        result = math.lcm(result, component)
    return result


def _pow_capped(base: int, exponent: int, cap: int) -> int:
    """base**exponent, capped at ``cap`` (never returns more than cap)."""
    if exponent == 0:
        return 1
    result = 1
    b = base
    while exponent:
        if exponent & 1:
            result *= b
            if result >= cap:
                return cap
        exponent >>= 1
        if exponent:
            b *= b
            if b >= cap:
                b = cap
    return min(result, cap)


def tower_value_capped(bases: Sequence[int], cap: int) -> tuple[int, bool]:
    """Evaluate a right-associative power tower, capped.

    Returns (value, at_least_cap). All generated bases are >= 2.
    """
    if not bases:
        raise ValueError("empty power tower")
    value = bases[-1]
    if value >= cap:
        return cap, True
    for base in reversed(bases[:-1]):
        if base == 0:
            value = 0 if value > 0 else 1
        elif base == 1:
            value = 1
        else:
            value = _pow_capped(base, value, cap)
            if value >= cap:
                return cap, True
    return value, value >= cap


def _crt(residues: Sequence[tuple[int, int]]) -> int:
    """Chinese remainder theorem for pairwise coprime moduli."""
    x = 0
    modulus = 1
    for residue, q in residues:
        t = ((residue - x) % q) * pow(modulus, -1, q) % q
        x += modulus * t
        modulus *= q
    return x % modulus


def tower_mod(bases: Sequence[int], mod: int) -> int:
    """Right-associative power tower modulo ``mod``.

    The tower is evaluated one prime power of ``mod`` at a time, then
    recombined with CRT. This avoids the non-coprime failure mode of the
    naive generalized-Euler shortcut while still handling towers whose full
    value cannot be materialized. For each prime power p^e:

    * if p divides the current base, the result is 0 once the remaining
      exponent is at least e (and is computed directly when it is smaller);
    * otherwise Euler's theorem reduces the exponent modulo phi(p^e).
    """
    if mod == 1:
        return 0
    if not bases:
        raise ValueError("empty power tower")
    if len(bases) == 1:
        return bases[0] % mod

    residues: list[tuple[int, int]] = []
    for p, e in factorize(mod).items():
        q = p**e
        residues.append((_tower_mod_prime_power(bases, p, e, q), q))
    return _crt(residues)


def _tower_mod_prime_power(
    bases: Sequence[int], p: int, e: int, q: int
) -> int:
    a = bases[0]
    rest = bases[1:]
    if a % p == 0:
        rest_value, rest_is_large = tower_value_capped(rest, e)
        if rest_is_large:
            return 0
        return pow(a, rest_value, q)

    phi = (p - 1) * (p ** (e - 1))
    rest_value, rest_is_large = tower_value_capped(rest, max(2, phi))
    if rest_is_large:
        exponent = tower_mod(rest, phi)
    else:
        exponent = rest_value
    return pow(a, exponent, q)


def format_power_tower(bases: Sequence[int]) -> str:
    if not bases:
        return ""
    expr = str(bases[-1])
    for base in reversed(bases[:-1]):
        expr = f"{base}^({expr})"
    return expr


def format_tower_expression(towers: Sequence[Sequence[int]], modulus: int) -> str:
    """Format a left-associated sum/product of power towers followed by 'mod m'."""
    if not towers:
        return f"0 mod {modulus}"
    expression = format_power_tower(towers[0])
    for i, tower in enumerate(towers[1:], start=1):
        op = "+" if i % 2 == 1 else "*"
        expression = f"({expression} {op} {format_power_tower(tower)})"
    return f"{expression} mod {modulus}"


# ---------------------------------------------------------------------------
# Human-readable linear systems.
# ---------------------------------------------------------------------------


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
