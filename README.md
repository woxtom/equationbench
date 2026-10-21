# EquationBench Linear

**How large a linear system can a model solve exactly?**

EquationBench is now a one-track benchmark. Every task is a dense integer linear
system with a unique solution. The benchmark measures the **50% frontier**: the
system size at which a model stops being reliably correct. The ladder is
open-ended, so the score has no ceiling.

> **Status:** v2 scoring core implemented. The ladder generator and frontier
> scorer are working and tested. The official staircase runner, model pilot, and
> frontier leaderboard are the next step. The multi-track v1 repository is
> preserved in the `v1-multitrack` git tag.

## Why this design

Fixed benchmarks saturate. Once every model solves the same 70 tasks, a 0–100
score becomes a history of the test set, not a measurement of capability.

EquationBench replaces the fixed set with a geometric ladder:

\[
n_L = \operatorname{round}\left(3 \cdot 2^{(L-1)/3}\right)
\]

| L | n | L | n | L | n | L | n |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 6 | 10 | 11 | 30 | 16 | 96 |
| 2 | 4 | 7 | 12 | 12 | 38 | 17 | 121 |
| 3 | 5 | 8 | 15 | 13 | 48 | 18 | 152 |
| 4 | 6 | 9 | 19 | 14 | 60 | 19 | 192 |
| 5 | 8 | 10 | 24 | 15 | 76 | 20 | 242 |

Each three levels doubles the system size. Coefficients are fixed in
`[-30, 30]` and solutions in `[-9, 9]`; **size is the only difficulty axis.**
That keeps the ladder interpretable and the scoring one-dimensional.

## The score

For each level, run 5 tasks. Apply a non-increasing isotonic regression to the
success curve, find the levels that bracket 50%, and interpolate:

\[
\log n^* = \log n_k + \frac{p_k - 0.5}{p_k - p_{k+1}}(\log n_{k+1} - \log n_k)
\]

\[
\text{EQB-L} = L^* = 1 + 3\log_2(n^*/3)
\]

`EQB-L` is the level at which the model has a 50% chance of exact success. It is
unbounded. Adding higher levels does **not** change an existing score; it only
extends the scale. If a model passes every attempted level, the score is reported
as `≥ Lmax` and the ladder is extended.

## Quick start

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone <this-repo> equationbench
cd equationbench
uv sync --extra dev

# Print the ladder
uv run eqb ladder --max-level 20

# Generate one real prompt per level to see measured token counts
uv run eqb ladder --max-level 10 --measure

# Machine-readable manifest
uv run eqb ladder --max-level 20 --json
```

Use the scorer directly:

```python
from equationbench.frontier import estimate_from_counts

score = estimate_from_counts({
    1: (5, 5), 2: (5, 5), 3: (5, 5), 4: (4, 5),
    5: (2, 5), 6: (0, 5),
})
print(score.score)      # 4.75
print(score.size)       # continuous geometric size
print(score.ci)         # bootstrap 95% interval
print(score.censored)   # None, "upper", "lower", or "ambiguous"
```

Generate a deterministic task:

```python
from equationbench.ladder import build_ladder_task

task = build_ladder_task(level=10, index=0)  # 24x24 system
print(task.metadata["n"], len(task.prompt), task.answer_type)
```

## Repository layout

```
src/equationbench/
  ladder.py          geometric ladder, deterministic task bank
  frontier.py        isotonic smoothing, 50% frontier, bootstrap CI
  generation/
    linear.py        dense integer systems, exact ground truth
  dataset.py         fixed-set dataset builder and sealed holdout support
  runner.py          provider runner (fixed-set path; staircase is next)
  scoring.py         legacy fixed-set scoring
  leaderboard.py     static site builder
  verify.py          exact answer parser and grader
  prompts.py         prompt contract
config/models.toml   pilot model slate
docs/
  ladder.md          protocol and scoring details
  polish-plan.md     cleanup and launch roadmap
tests/               generator, scorer, parser, runner, and CLI tests
```

## What is next

1. Wire the ladder staircase into `runner.py` (`eqb run-frontier`).
2. Run the pilot slate: 5 tasks at L6/L8/L10, two repeats, measure stability and
   provider-error rates.
3. Build the frontier leaderboard: frontier curve, Pareto chart, budget table.
4. Run the first clean official rows and deploy the site.

See [`docs/polish-plan.md`](docs/polish-plan.md) for the full plan.

## The v1 archive

The seven-track v1 benchmark, its datasets, runs, and generated leaderboards are
preserved in the `v1-multitrack` git tag. They are not comparable to v2 and are
not part of the current package.

## License

MIT. See [LICENSE](LICENSE).
