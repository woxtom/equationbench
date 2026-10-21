# Task Tracks

EquationBench has seven tracks and five difficulty levels. The public test set is **70 tasks** (2 per family × level); the development set is **35** (1 per cell); the sealed holdout is **140** (4 per cell).

The examples below are from the public development set. The exact parameter tables live in `src/equationbench/generation/<family>.py` and are reproduced here for convenience.

## Summary

| Track | Core operation | Answer | Level 5 shape |
|---|---|---|---|
| Arithmetics | Evaluate nested integer expression | Integer | 90 operators, powers, factorials |
| Polynomial Algebra | Coefficient extraction from a product | Integer | degree 36 |
| Linear Systems | Solve \(A x = b\) | Integer vector | 14 variables |
| Calculus | Differentiate or integrate exactly | Rational | degree 22 |
| Modular Arithmetic | Power towers modulo a prime | Integer | height 5, 3 towers, modulus \(10^9+7\) |
| Matrix Algebra | Exact determinant | Integer | 10×10 \(\det(A^2+cA+dI)\) |
| Recurrences | High-index linear recurrence | Integer modulo \(p\) | order 5, \(N \approx 10^{18}\) |

## Difficulty levels

| Level | Label | Intent |
|---:|---|---|
| 1 | Warm-up | Short state, one or two familiar steps |
| 2 | Working | Multi-step arithmetic or a small system |
| 3 | Hard | Large intermediate state; requires a disciplined plan |
| 4 | Very hard | Frontier-scale state; naive step-by-step work is error-prone |
| 5 | Frontier | Near the limit of a single closed-book response |

Levels are weights in the EQB Score, not a claim that every level-5 instance is harder than every level-4 instance. The leaderboard reports empirical accuracy by level as the calibration check.

---

## 1. Arithmetic (`arith`)

Fully parenthesized integer expressions built from addition, subtraction, multiplication, exponentiation, and factorials. Levels 4–5 add factorial leaves and nested powers. Expressions are evaluated with Python big integers; results can have hundreds of digits.

| Level | Operators | Leaf bound | Max exponent | Factorials | Power probability |
|---:|---:|---:|---:|---|---:|
| 1 | 6 | 10 | 3 | no | 0.00 |
| 2 | 14 | 100 | 3 | no | 0.00 |
| 3 | 26 | 1,000 | 4 | no | 0.10 |
| 4 | 48 | 10,000 | 4 | yes | 0.14 |
| 5 | 90 | 100,000 | 5 | yes | 0.18 |

**Example — level 3**

```
Evaluate the following integer expression exactly.

((970^2 - (454 * ((258 + 782) - 256))) + (((((297 + 954) * 38) *
((((648 - 42) * (785 * 955)) * ((((((694 * 721) * 571) - 998) *
(373 + 958)) - ((669 * (213 - 801)) * (910 + 520))) * 926))))^4 * 19))
```

The exact answer is a 110-digit integer.

**What it tests:** maintaining order of operations and exact magnitude across dozens of nested operations; resisting the temptation to approximate.

---

## 2. Polynomial Algebra (`poly`)

A product of many linear factors. The model must extract one exact coefficient, which can be computed by dynamic programming over the factors or by elementary symmetric polynomials.


| Level | Degree | Coeff bound |
|---:|---:|---:|
| 1 | 5 | 5 |
| 2 | 8 | 9 |
| 3 | 12 | 15 |
| 4 | 20 | 25 |
| 5 | 36 | 50 |

**Example — level 3**

```
P(x) = (-9x + 4)(2x + 13)(-5x - 7)(-11x + 11)(14x - 7)(-8x - 4)
       (13x + 2)(15x - 6)(7x + 3)(8x - 13)(-10x - 7)(13x + 6)

Compute the coefficient of x^7 in the expansion of P(x).
```

**What it tests:** combinatorial coefficient reasoning, sign management, and exact integer arithmetic over many factors.

---

## 3. Linear Systems (`linear`)

Dense integer systems constructed from a known integer solution. The matrix is checked to be nonsingular. The model must return the exact solution vector in order.

| Level | Variables | Coeff bound | Solution bound |
|---:|---:|---:|---:|
| 1 | 3 | 5 | 5 |
| 2 | 4 | 9 | 7 |
| 3 | 6 | 12 | 9 |
| 4 | 9 | 20 | 9 |
| 5 | 14 | 30 | 9 |

**Example — level 3**

```
-10*x1 - 2*x2 - 11*x3 - 3*x4 - x5 + 3*x6 = 36
9*x1 - 3*x2 - 3*x3 + 12*x4 - 12*x5 + 4*x6 = 152
-11*x1 + 10*x2 + 10*x3 + x4 - 7*x5 - 6*x6 = -66
-5*x1 + 2*x2 + 6*x3 + 6*x4 - 4*x5 + 2*x6 = 1
10*x1 + x2 - 10*x3 + 3*x5 - 9*x6 = 108
5*x1 + 5*x2 - 2*x3 + 4*x4 - 9*x5 + 5*x6 = 109

Give the solution as [x1, x2, ..., x6].
```

**What it tests:** Gaussian elimination under exact arithmetic, variable ordering, and error detection in a long elimination.

---

## 4. Calculus (`calculus`)

A factored polynomial and either a high-order derivative at a point or a definite integral over an integer interval. Levels 1–3 are derivatives; levels 4–5 are integrals.

| Level | Degree | Coeff bound | Mode | Derivative order |
|---:|---:|---:|---|---:|
| 1 | 4 | 5 | derivative | 1 |
| 2 | 6 | 9 | derivative | 1 |
| 3 | 9 | 12 | derivative | 2 |
| 4 | 14 | 20 | integral | — |
| 5 | 22 | 30 | integral | — |

**Example — level 3**

```
f(x) = (-4x - 4)(9x - 11)(11x - 2)(-4x - 4)(-8x - 2)
       (6x - 4)(2x - 8)(8x + 7)(4x - 8)

Compute the second derivative of f at x = -4. Give the exact value.
```

**What it tests:** expanding a large product, differentiating or integrating termwise, and keeping exact rational arithmetic through a definite integral.

---

## 5. Modular Arithmetic (`modular`)

Mixed expressions containing right-associative power towers. The tower is evaluated from the top down; the final `mod m` applies to the entire expression. Levels 2–5 require Euler/CRT reasoning rather than materializing the tower.

| Level | Modulus | Tower height | Towers | Base max | Top exponent max |
|---:|---:|---:|---:|---:|---:|
| 1 | 1,009 | 2 | 1 | 9 | 9 |
| 2 | 1,000,003 | 3 | 1 | 12 | 12 |
| 3 | 1,000,003 | 3 | 2 | 15 | 15 |
| 4 | 1,000,000,007 | 4 | 2 | 20 | 20 |
| 5 | 1,000,000,007 | 5 | 3 | 32 | 32 |

**Example — level 3**

```
E = (6^(6^(3)) + 12^(7^(15))) mod 1000003
```

**What it tests:** recognizing that the exponent cannot be materialized, reducing modulo prime powers, and recombining residues correctly.

---

## 6. Matrix Algebra (`matrix`)

Exact determinants of integer matrices, and at levels 4–5 determinants of matrix polynomials such as \(A^2+cA+dI\). The determinant is computed with fraction-free Bareiss elimination.

| Level | Size | Entry bound | Mode |
|---:|---:|---:|---|
| 1 | 3×3 | 3 | \(\det(A)\) |
| 2 | 4×4 | 5 | \(\det(A)\) |
| 3 | 5×5 | 7 | \(\det(A)\) |
| 4 | 7×7 | 9 | \(\det(A^2+cA+dI)\) |
| 5 | 10×10 | 12 | \(\det(A^2+cA+dI)\) |

**Example — level 3**

```
A =
[  6  0 -2  5  6 ]
[ -5 -7  7 -4 -7 ]
[ -3  6  2 -1 -1 ]
[ -2  7  3 -2  4 ]
[  6 -6 -3  2 -1 ]

Compute det(A).
```

**What it tests:** matrix algebra, elimination with large integer pivots, and (at higher levels) composing a matrix polynomial before taking the determinant.

---

## 7. Recurrences (`recurrence`)

A constant-coefficient linear recurrence with an initial state, evaluated at a very large index modulo a prime. The model must use fast exponentiation or a closed-form/Kitamasa approach; direct iteration is impractical.

| Level | Order | Index range | Modulus | Coeff bound |
|---:|---:|---|---:|---:|
| 1 | 2 | 5–20 | 1,009 | 5 |
| 2 | 2 | 100–1,000 | 1,000,003 | 9 |
| 3 | 3 | 1,000,000–10,000,000 | 1,000,000,007 | 9 |
| 4 | 4 | \(10^{12}\)–\(10^{13}\) | 998,244,353 | 12 |
| 5 | 5 | \(10^{18}\)–\(9\times10^{18}\) | 1,000,000,007 | 15 |

**Example — level 3**

```
a_0 = 2, a_1 = 7, a_2 = 9

a_n = -8*a_(n-1) + 5*a_(n-2) + 5*a_(n-3)

Compute a_3089001 mod 1000000007.
```

**What it tests:** recognizing a linear recurrence, building the companion matrix or polynomial exponentiation, and carrying modular reductions through a logarithmic number of matrix multiplications.

---

## Linear-only profile

For cost-controlled experiments, the linear track can be generated and scored on
its own:

```bash
eqb build-dataset --profile linear-test
eqb run --model deepseek-v4-1-flash \
  --dataset datasets/equationbench-v1-test-linear \
  --thinking max --timeout 0
eqb leaderboard build \
  --runs runs/linear \
  --dataset datasets/equationbench-v1-test-linear \
  --out leaderboard-linear
```

The linear test profile has **10 tasks** (2 per level) and the development
profile has **5** (1 per level). They use the same master seeds and task ids as
the corresponding linear tasks in the full public set, so they are directly
comparable to the linear subset of a full run. The dataset hash is different
because the manifest contains only one family.

## Answer types and grading

| Type | Example answer | Parser accepts |
|---|---|---|
| Integer | `639353543010031489…` | JSON string, bare integer, exact expression |
| Rational | `521783505659087827/1001` | `p/q`, LaTeX `\frac{p}{q}`, exact decimal, integer |
| Integer vector | `[3, 6, -9, 9, 0, 2]` | JSON array, tuple, `x1 = 3, x2 = 6, …` |

All values are canonicalized before comparison. There is no tolerance and no partial credit. See [methodology.md](methodology.md#4-prompt-and-answer-contract).

## Prompt size

"Large" in EquationBench refers primarily to the computational state, not to raw context length. Public test statistics are generated at build time and shown on the leaderboard. Typical prompts are hundreds to a few thousand characters; the hard part is the exact computation, not reading the prompt.

## Regenerating examples

```bash
eqb verify-dataset --path datasets/equationbench-v1-dev
eqb show-task --family calculus --level 4 --solution
eqb build-dataset --profile dev --out /tmp/eqb-dev --per-cell 1 --force
```
