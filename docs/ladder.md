# The Linear Ladder and Frontier Score

**Version:** ladder v1 · scoring v2 (frontier) · status: scaffolding

This document specifies the open-ended linear ladder: how tasks are generated,
how the frontier score is computed, and what the public protocol will require.
The implementation lives in `src/equationbench/ladder.py` and
`src/equationbench/frontier.py`.

## 1. Task

Every task is a dense integer linear system

$$
A x = b, \qquad A \in [-30,30]^{n \times n}, \quad x \in [-9,9]^n
$$

with a unique solution. The generator picks $A$, rejects singular matrices,
picks a known integer solution $x$, computes $b = Ax$, and asks for the
solution vector. Ground truth is exact; there is no tolerance and no judge.

The answer is a JSON integer list:

```json
{"answer": [3, -1, 7]}
```

## 2. Ladder

The level is a geometric function of the system size:

$$
n_L = \mathrm{round}\left(3 \cdot 2^{(L-1)/3}\right)
$$

| L | n | L | n | L | n | L | n |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 6 | 10 | 11 | 30 | 16 | 96 |
| 2 | 4 | 7 | 12 | 12 | 38 | 17 | 121 |
| 3 | 5 | 8 | 15 | 13 | 48 | 18 | 152 |
| 4 | 6 | 9 | 19 | 14 | 60 | 19 | 192 |
| 5 | 8 | 10 | 24 | 15 | 76 | 20 | 242 |

Three levels double the system size. Equal level steps are equal steps in
$\log n$, which is the natural difficulty scale for dense elimination.

The coefficient and solution bounds are fixed. **Size is the only difficulty
axis.** If the frontier turns out to be too easy or too hard, adjust the bound
once in a pilot and freeze it for the season; do not scale it per level.

## 3. Task bank

For each level $L$ and index $j = 1,\dots,10$, a deterministic seed is derived
from

```
(season_seed, "linear", L, j, generator_version, prompt_version)
```

- Indices 1–5 are the **core bank**.
- Indices 6–10 are the **precision bank**, used at the two bracket levels.

All models answer the same tasks at a level. The public season seed makes every
task reproducible; the sealed holdout uses a different seed so it can verify top
rows and later seasons.

Generate any level:

```bash
uv run eqb ladder --max-level 20
uv run eqb ladder --max-level 10 --measure
```

```python
from equationbench.ladder import build_ladder_task

task = build_ladder_task(level=10, index=0)
```

## 4. Frontier score

For a model, at each tested level $L$:

- $k_L$ valid tasks, $c_L$ correct,
- $p_L = c_L / k_L$,
- apply non-increasing isotonic regression to get $\hat p_L$.

Find adjacent levels $k, k+1$ with

$$
\hat p_k \ge 0.5 > \hat p_{k+1}.
$$

Interpolate in $\log n$:

$$
\log n^* = \log n_k +
\frac{\hat p_k - 0.5}{\hat p_k - \hat p_{k+1}}
\left(\log n_{k+1} - \log n_k\right)
$$

Then

$$
\text{EQB-L} = L^* = 1 + 3\log_2(n^*/3).
$$

`EQB-L` is the continuous level at which the model has a 50% chance of exact
success. It has no upper bound.

### Why the score stays consistent

- **Extension invariance:** if the bracket is at L7/L8, adding L9–L30 does not
  change the score.
- **No dilution:** adding tasks or levels does not mechanically lower scores.
- **Incremental:** old rows do not need rerunning when a new level is added.
- **Censoring is explicit:** all-pass is reported as `≥ Lmax`, not a fake finite
  number.
- **Physical unit:** $n^*$ is the system size; $L^*$ is a log-scale label.

### Confidence intervals

Bootstrap tasks within each level, rerun isotonic regression, recompute
$\log n^*$, and take the 2.5–97.5 percentiles. Use paired bootstrap across
models so all models see the same resampled tasks. With 5 tasks per level, the
interval is wide; run 5 extra tasks at each of the two bracket levels before
stopping.

### Edge cases

| Case | Result |
|---|---|
| `p_1 < 0.5` | `censored="lower"`, upper bound at L1 |
| bracket at `k/k+1` | finite `L*` plus CI |
| every tested level passes | `censored="upper"`, lower bound at Lmax |
| flat 50% curve | `censored="ambiguous"`, midpoint |
| final 0.5 plateau (e.g. 2/5 then 3/5) | `censored="ambiguous"`, plateau midpoint; tested max as bound |
| fewer than 3 valid tasks at a level | level incomplete; not used for the bracket |
| prompt exceeds context | `not_testable`; not a wrong answer |

## 5. Run protocol

The staircase, once wired into the runner, is:

```
for L = 1, 2, 3, ...:
    run 5 core tasks at level L
    fit the isotonic curve
    if the 50% point is bracketed at (L-1, L):
        run 5 precision tasks at L-1 and L
        stop
    if p_L >= 0.5:
        continue
    else:
        stop
```

Start at L1 for every model. A model that fails early is cheap to measure; a
model that goes far pays for the levels it reaches. If a model passes the public
cap, continue into extension levels until it fails or hits the context/cost cap.

### Missing data

- `provider_error`, `timeout`, `missing` → retry; if still failing, mark `infra`
  and exclude from the denominator.
- `wrong`, `unparseable`, `refusal` → 0 (model behavior).
- Require at least 3 valid tasks per level.
- A run with too many infra failures is `unstable` and not ranked.
- Report completion rate and provider-error rate next to every row.

## 6. Cost

Report capability and cost side by side:

- cost to frontier (actual spend for the staircase),
- effective cost (spend including retries / valid completed tasks),
- cost per 100 valid tasks,
- input/output/reasoning/total tokens,
- cost basis (`api_list`, `subscription_amortized`, `free`, `unknown`).

The useful views are the Pareto frontier, "best under $X", and "cheapest model
that reaches L8/L10/L12". Do not collapse capability and cost into one arbitrary
composite as the primary rank.

## 7. Versioning

- A ladder change bumps `LADDER_VERSION` and `GENERATOR_VERSION`.
- A prompt change bumps `PROMPT_VERSION`.
- A scoring change bumps `SCORING_VERSION`.
- A new season rotates the seed and starts a new leaderboard season.
- Rows are comparable only within the same ladder, prompt, scoring, and season
  versions.
