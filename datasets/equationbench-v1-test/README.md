# EquationBench v1 — test set

Public evaluation set used for the open leaderboard.

- Tasks: **70** (2 per family × level)
- Dataset hash: `91b398a7ea4d28d94a23bb14d505476f830fc60ce3ee75c5d5d63d44abccadf4`
- Master seed: `731992`
- Generator: `1.0.0` · Prompt: `1.0`

| Family | Track | Tasks |
|---|---|---:|
| `arith` | Arithmetic | 10 |
| `poly` | Polynomial Algebra | 10 |
| `linear` | Linear Systems | 10 |
| `calculus` | Calculus | 10 |
| `modular` | Modular Arithmetic | 10 |
| `matrix` | Matrix Algebra | 10 |
| `recurrence` | Recurrences | 10 |

`tasks.jsonl` includes answers and short solutions. `prompts.jsonl` is the
model-facing subset. The private holdout is generated separately from an
unpublished seed and is not in this directory.
