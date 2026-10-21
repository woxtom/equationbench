# EquationBench v1 — dev set

Public development set: one task per family/level cell.

- Tasks: **35** (1 per family × level)
- Dataset hash: `9c987856c29930148f686aa98e350c875d2ac96ddab01782cf6db40b7f90e1e8`
- Master seed: `20261017`
- Generator: `1.0.0` · Prompt: `1.0`

| Family | Track | Tasks |
|---|---|---:|
| `arith` | Arithmetic | 5 |
| `poly` | Polynomial Algebra | 5 |
| `linear` | Linear Systems | 5 |
| `calculus` | Calculus | 5 |
| `modular` | Modular Arithmetic | 5 |
| `matrix` | Matrix Algebra | 5 |
| `recurrence` | Recurrences | 5 |

`tasks.jsonl` includes answers and short solutions. `prompts.jsonl` is the
model-facing subset. The private holdout is generated separately from an
unpublished seed and is not in this directory.
