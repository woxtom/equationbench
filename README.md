# EquationBench Linear

**How large a linear system can a model solve exactly?**

One question, one leaderboard. Every task is a dense integer linear system with
a unique solution. The score is the **50% frontier**: the system size at which a
model stops being reliably correct. The ladder is open-ended, so there is no
ceiling.

> **Unofficial.** Not peer-reviewed, not an official evaluation, and not a
> measure of general mathematical ability. It measures one thing: how large an
> integer linear system a model can solve exactly, in one prompt, with no tools.
> Every row links to a run receipt you can regenerate from the published seed.
>
> **Status:** v2 scoring core works and is tested. The staircase runner, the
> pilot slate, and the first published rows are not done yet. Nothing on the
> leaderboard is final until it has a receipt.

## Why a ladder

Fixed test sets saturate. Once every model solves the same 70 tasks, a 0–100
score records the history of that test set, not what the model can do.

So the difficulty axis is not *topic*, it is *size*:

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

Three levels double the size. Coefficients are fixed in `[-30, 30]` and
solutions in `[-9, 9]`. Size is the only thing that changes, which is what makes
a single number meaningful.

The task: given `A` and `b = A·x`, return the integer vector `x`.

```json
{"answer": [3, -1, 7]}
```

Exact comparison after canonicalization. No judge, no tolerance band, no partial
credit. Off by one is wrong.

## The score

Run 5 tasks per level. Smooth the success curve with non-increasing isotonic
regression, find the levels that bracket 50%, and interpolate:

\[
\log n^* = \log n_k + \frac{p_k - 0.5}{p_k - p_{k+1}}(\log n_{k+1} - \log n_k)
\]

\[
\text{EQB-L} = L^* = 1 + 3\log_2(n^*/3)
\]

`EQB-L` is the level where the model has a 50% chance of an exact solve. It is
unbounded. Adding higher levels does **not** change an existing score; it only
extends the scale. A model that passes everything tested is reported as
`≥ Lmax`, and the ladder gets longer.

Read it as *"this model is good to about a 24×24 exact integer system, alone,
with no calculator."* Not as an IQ score.

## First pilot (not official)

A first fixed-ladder pilot used DeepSeek V4.1 Flash at max reasoning, 5 tasks
per level, levels L5–L10:

| Level | n | Correct | Cost | Median latency |
|---:|---:|---:|---:|---:|
| L5 | 8 | 5/5 | $0.18 | 106s |
| L6 | 10 | 5/5 | $0.22 | 138s |
| L7 | 12 | 5/5 | $0.29 | 133s |
| L8 | 15 | 5/5 | $0.44 | 206s |
| L9 | 19 | 2/5 | $0.84 | 351s |
| L10 | 24 | 3/5 | $1.20 | 617s |

Result: **EQB-L 9.5**, frontier about 21×21, 95% CI 8.6–9.75, **$3.16**,
1h23m wall time, 100% valid, no provider errors.

The L9/L10 pair is non-monotonic (2/5 then 3/5), so isotonic regression pools
them into a 0.5 plateau and the score is marked `ambiguous`, with L10 as the
tested upper bound. The next step is to run L11 and the precision bank to turn
that plateau into a finite bracket. This is a pilot, not an official row.

## Quick start

Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev

# Print the ladder
uv run eqb ladder --max-level 20

# One real prompt per level, with measured token counts
uv run eqb ladder --max-level 10 --measure

# Machine-readable manifest
uv run eqb ladder --max-level 20 --json
```

Score a run without calling any model:

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

Regenerate a task — this is the whole point of the published seed:

```python
from equationbench.ladder import build_ladder_task

task = build_ladder_task(level=10, index=0)  # 24x24 system
print(task.metadata["n"], len(task.prompt), task.answer_type)
```

## What a row has to show

A number without a receipt is not a result. Each published row carries:

- the exact prompt and raw response for every task
- token counts, provider-reported cost, latency
- the dataset hash and the seed/version tuple
- timeouts and provider errors listed **separately** from wrong answers, and
  excluded from the denominator
- the completion rate, because a model that times out is not a model that
  failed

Subscription limits, 5-hour windows, and rate limits get named when they happen.
If a row was stopped halfway, it says so.

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
  verify.py          exact answer parser and grader
  prompts.py         prompt contract
config/models.toml   pilot model slate
docs/
  ladder.md          protocol and scoring details
  methodology.md     exactness, generation, reproducibility
  leaderboard.md     how the frontier table will read
  submission.md      how to submit a run
  polish-plan.md     cleanup and launch roadmap
tests/               generator, scorer, parser, runner, and CLI tests
```

## What is next

1. Wire the staircase into `runner.py` (`eqb run-frontier`).
2. Pilot: 5 tasks at L6/L8/L10, two repeats, to measure stability and error
   rates.
3. Frontier curve, Pareto chart, and budget table for the site.
4. Publish the first clean rows.

See [`docs/polish-plan.md`](docs/polish-plan.md).

## The v1 archive

An earlier seven-track version (linear systems, polynomial expansion, recurrences
above 10^18, matrix-polynomial determinants, exponent towers, calculus) is
preserved at tag `v1-multitrack`. Different tasks, different score, not
comparable. It is kept because the numbers exist, not because they mean anything
today.

## License

MIT. See [LICENSE](LICENSE).
