# The Linear Ladder and EQB Score

**Version:** ladder v1 · scoring v3.0 · public horizon: L11

The ladder is open-ended; each published comparison has one shared scoring
horizon. Implementation: `src/equationbench/ladder.py`, `area.py`, and
`ladder_run.py`. The v2 frontier estimator is legacy code, not the current rank.

## 1. Task

Every task is a dense integer linear system

$$
Ax=b,\qquad A\in[-30,30]^{n\times n},\quad x\in[-9,9]^n.
$$

The generator draws a nonsingular matrix, picks a known integer solution, and
computes `b = A·x`. The model receives one prompt, no tools, and returns:

```json
{"answer": [3, -1, 7]}
```

Exact comparison after canonicalization. No judge, tolerance, or partial credit.

## 2. Ladder

$$
n_L=\mathrm{round}\left(3\cdot2^{(L-1)/3}\right).
$$

| L | n | L | n | L | n | L | n |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 6 | 10 | 11 | 30 | 16 | 96 |
| 2 | 4 | 7 | 12 | 12 | 38 | 17 | 121 |
| 3 | 5 | 8 | 15 | 13 | 48 | 18 | 152 |
| 4 | 6 | 9 | 19 | 14 | 60 | 19 | 192 |
| 5 | 8 | 10 | 24 | 15 | 76 | 20 | 242 |

Three ideal levels double the size. Coefficient and solution bounds stay fixed;
size is the only difficulty axis. Because sizes are rounded, the score uses
actual log-size coordinates, not nominal level labels:

$$
x_L=1+3\log_2(n_L/3).
$$

For example, `x_10 = 10`, while `x_11 ≈ 10.9658`.

## 3. Task bank and scoring grid

The public season seed is `731992`. Each task is deterministic from the seed,
family, level, index, generator version, and prompt version. The core bank has
5 tasks per level; a precision bank adds up to 5 more. Models use the same tasks
at a given level. A sealed holdout is planned, not implemented.

**Scoring v3 uses only whole levels L1 through the shared horizon H.** For the
current leaderboard, `H = 11`. Extra trials refine per-level rate estimates;
they do not directly increase a level's integration weight.

Half levels such as L9.5 (21 variables) remain available as diagnostics. They
are excluded from fitting, integration, and bootstrap. They must not give a
selectively sampled run a different scoring grid. Outcomes above H are likewise
excluded and listed in `ignored_levels`.

```bash
uv run eqb ladder --max-level 20
uv run eqb ladder --max-level 10 --measure
```

## 4. One score: effective solved levels

At each observed scoring level, let `c_L` be correct answers and `k_L` valid
answers. Estimate `p_L = c_L / k_L`, then apply non-increasing isotonic
regression weighted by `k_L`. This pools noisy upward reversals.

Interpolate the fitted rates linearly between every adjacent whole-level knot
in the actual log-size coordinates `x_L`. Then:

$$
\boxed{\mathrm{EQB}=1+\int_1^{x_H}\hat p(x)\,dx}
$$

The exact implementation is a trapezoidal sum:

$$
\mathrm{EQB}=1+\sum_{L=1}^{H-1}
(x_{L+1}-x_L)\frac{\hat p_L+\hat p_{L+1}}2.
$$

Higher is better. One unit of log difficulty solved with 60% probability adds
0.6 points. This combines reach and reliability without a moving band, a
frontier multiplier, or normalization by the number of tasks/levels. It is
**not** a system size, a percentage, or a 50% frontier.

- Improving an outcome cannot lower the score on a fixed grid with fixed trial counts.
- Adding all-zero tail levels does not dilute the area.
- At a fixed H the score is between 1 and `x_H`. The baseline 1 is a coordinate
  offset, not credit for solving a task; all-fail from L1 scores 1.
- All-pass through H scores `x_H`: a horizon ceiling, not unlimited ability.
  Nonzero success at H is flagged as a reason to consider extending the horizon.
- Extending H is a shared, versioned protocol change. Re-score all rows together;
  never compare scores from different horizons. New positive-tail evidence can
  change an old estimate. There is no permanent ceiling across protocol versions.
- Exactly equal point estimates share a rank. Cost, effort labels, and overall
  accuracy do not break score ties.

### Missing levels: identification bounds, not fabricated answers

Every whole-level knot must be identified before assigning a ranked point score.
For a missing knot, monotonicity supplies:

- a lower rate from the nearest observed harder knot, or 0 if none exists;
- an upper rate from the nearest observed easier knot, or 1 if none exists.

Integrate the lower and upper completed curves separately. If any knot remains
unresolved, publish `score=null`, `censored="incomplete"`, and `score_bounds`;
the row is unranked. These are bounds conditional on the fitted observed rates,
**not** confidence intervals for the true probabilities.

Equal bounds identify a missing knot under the monotone model. For example, a
fitted 100% first observation identifies its easier prefix at 100%; a fitted
zero final observation identifies its harder suffix at zero. A missing knot
between equal fitted rates is also identified. These inferences are disclosed
in `inferred_levels`, not represented as observed trials. A missing knot between
different fitted rates remains unresolved; it is not silently interpolated away.

This is an empirical estimation convention, not proof of perfect or zero true
success. New runs should measure the full grid, especially endpoint levels.

### Confidence intervals

Resample valid task outcomes within each observed whole level, refit isotonic
rates, and recompute the entire area. Use deterministic seeded bootstrap draws
(default 2,000) and the 2.5th/97.5th percentiles. If a replicate has unresolved
knots, retain its lower and upper integrals instead of discarding it. Point-score
intervals use the lower-tail percentile of lower integrals and the upper-tail
percentile of upper integrals. Bounds-only rows do not receive a point-score CI.

These intervals are conditional on the grid and fitting assumptions. All-pass
or all-fail samples have no nonparametric bootstrap variance, so small banks can
understate uncertainty, even without a fully degenerate interval. They do not
capture provider drift, adaptive sampling, or endpoint extrapolation error.
Pairwise significance requires a separate matched-task analysis; overlapping
or non-overlapping marginal intervals alone are not that analysis.

## 5. Run protocol

```bash
uv run eqb run-ladder --model deepseek-v4-1-flash --levels 1-11 --thinking max
uv run eqb score --run runs/path/to/receipt
uv run eqb build-leaderboard
uv run eqb build-leaderboard --check
```

- Prefer full L1–L11 coverage with at least 5 core tasks per level.
- Use a predeclared precision allocation; do not stop merely because 50% is crossed.
- The adaptive runner is not implemented. Choose levels explicitly; omissions
  can produce unranked bounds rather than a score.
- Require at least 3 valid trials at every observed scoring level.
- Official rows require a complete run, valid regenerated hash, direct provider,
  max effort, and 100% valid coverage. Provisional rows require at least 90%.
- Provider errors, timeouts, and missing responses are excluded from per-level
  accuracy and reduce coverage. Wrong answers, refusals, and unparseable model
  answers count as failures. Preserve the existing infrastructure classifications.
- Cost/context stops do not imply failure at untested levels.
- `--horizon` is available for experiments; the published builder always uses
  the season's shared horizon. A custom-horizon score is not comparable.

`eqb.json` and `summary.json["eqb"]` contain the v3 score. The historical
`run-frontier` command is a hidden compatibility alias for `run-ladder`, not a
way to compute the old rank. Old receipts and `frontier.json` artifacts remain
historical; the leaderboard recomputes from predictions rather than trusting them.

## 6. Cost and versioning

Show total run spend, coverage, tokens, and latency alongside capability.
Different task coverage affects cost, so cost charts are descriptive, not a
standardized cost-to-capability experiment. Never put price into EQB.

Ladder changes bump `LADDER_VERSION` and `GENERATOR_VERSION`; prompt changes bump
`PROMPT_VERSION`; scoring changes bump `SCORING_VERSION`. A new season rotates
the seed. Comparability requires the same ladder, prompt, scoring, horizon, and
season. The v2 frontier/composite scores are not comparable to v3 EQB.
