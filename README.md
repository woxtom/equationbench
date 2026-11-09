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
> **Site:** <https://woxtom.github.io/equationbench/>
>
> **Status:** v2 scoring core works and is tested. Two official max-effort rows
> and one combined leaderboard are published. The adaptive staircase is not wired
> yet. Nothing is final without a receipt.

## Why a ladder

Fixed test sets saturate. Once every model solves the same 70 tasks, a 0–100
score records the history of that test set, not what the model can do.

So the difficulty axis is not *topic*, it is *size*:

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

$$
\log n^* = \log n_k + \frac{p_k - 0.5}{p_k - p_{k+1}}(\log n_{k+1} - \log n_k)
$$

$$
\text{EQB-L} = L^* = 1 + 3\log_2(n^*/3)
$$

`EQB-L` is the level where the model has a 50% chance of an exact solve. It is
unbounded. Adding higher levels does **not** change an existing score; it only
extends the scale. A model that passes everything tested is reported as
`≥ Lmax`, and the ladder gets longer.

Read it as *"this model is good to about a 24×24 exact integer system, alone,
with no calculator."* Not as an IQ score.

## Leaderboard (2026-10)

Season seed `731992` · ladder v1. One table, all runs.

`EQB-C = EQB-L × Band` is the ranked composite. `EQB-L` is the 50% frontier.
`Band` is the exact-solve rate over the whole levels `floor(EQB-L) − 1` to
`floor(EQB-L) + 1`. `Solved` is exact answers divided by all tasks.
`Cover` is valid tasks divided by all tasks.

<!-- leaderboard:start -->
| # | Model | Effort | Status | EQB-C | EQB-L (95% CI) | Solved | Band | Cover | Tokens | Cost | Note |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | [GPT-6 Astra](runs/provisional/2026-10/astra/openai-gpt-6-astra-high) | high | Provisional | 7.06 | 10.59 (10.32–10.74) | 18/25 | 67% (L9–L11) | 100% | 515k | $22.70 |  |
| 2 | [GPT-6.1 Sol](runs/provisional/2026-10/high/openai-gpt-6-1-sol-core5) | high | Provisional | 6.84 | 10.25 (9.66–10.66) | 29/40 | 67% (L9–L11) | 90% | 567k | $5.06* | 4 provider timeout(s) |
| 3 | [GPT-6.1 Terra](runs/official/2026-10/openai-gpt-6-1-terra) | max | Official | 5.40 | 10.13 (9.71–10.59) | 57/75 | 53% (L9–L11) | 100% | 1.41M | $6.45 |  |
| 4 | [DeepSeek V4.1 Flash](runs/provisional/2026-10/high/deepseek-v4-1-flash) | high | Provisional | 4.66 | 9.31 (8.73–9.77) | 27/50 | 50% (L8–L10) | 100% | 4.49M | $5.28 |  |
| 5 | [GPT-6 Astra](runs/provisional/2026-10/astra/openai-gpt-6-astra-medium) | medium | Provisional | 4.04 | 7.58 (7.45–7.66) | 18/40 | 53% (L6–L8) | 100% | 178k | $5.98 |  |
| 6 | [DeepSeek V4.1 Flash](runs/official/2026-10/deepseek-v4-1-flash) | max | Official | 3.67 | 10.00 (8.82–10.54) | 52/75 | 37% (L9–L11) | 100% | 7.54M | $8.91 |  |
| 7 | [GPT-6 Astra](runs/provisional/2026-10/astra/openai-gpt-6-astra-low) | low | Provisional | 3.59 | 6.73 (6.05–6.81) | 12/40 | 53% (L5–L7) | 100% | 131k | $3.69 |  |
| 8 | [GPT-6.1 Terra](runs/provisional/2026-10/high/openai-gpt-6-1-terra) | high | Provisional | 2.86 | 4.29 (3.87–4.48) | 10/25 | 67% (L3–L5) | 100% | 43k | $0.16 |  |
| 9 | [GPT-6 Luna](runs/provisional/2026-10/high/openai-gpt-6-luna) | high | Provisional | 2.28 | 3.80 (3.41–4.47) | 6/20 | 60% (L3–L4) | 100% | 86k | $0.04 |  |
| 10 | [GLM-5.3 Flash](runs/provisional/2026-10/high/zai-glm-5-3-flash) | high | Provisional | 2.22 | 3.70 (3.61–4.21) | 6/20 | 60% (L3–L4) | 100% | 599k | $0.30 |  |
| — | [Claude Haiku 5.5 (OpenRouter)](runs/provisional/2026-10/openrouter/anthropic-claude-haiku-5-5-high) | high | Unranked | — | ≥8.0 | 11/30 | — | 40% | 1.74M | unknown | 5 response(s) hit the output token cap |
| — | [GPT-5.6 Luna](runs/provisional/2026-10/openai-gpt-5-6-luna) | max | Unranked | — | ≥8.0 | 36/55 | — | 65% | 2.15M | unknown | 7 response(s) hit the output token cap |
| — | [Gemini 4 Argon](runs/provisional/2026-10/gemini/google-gemini-4-argon-high) | high | Unranked | — | ≥9.0 | 7/15 | — | 60% | 533k | $5.16* | cost excludes 3 call(s) with no cost record |
| — | [MiMo v2.6 Flash](runs/provisional/2026-10/high/xiaomi-mimo-v2-6-flash) | high | Unranked | — | ≥5.0 | 13/20 | — | 65% | 573k | unknown | 2 provider timeout(s) |
<!-- leaderboard:end -->

**How to read it**

- Ranked rows are sorted by `EQB-C`. `EQB-L` is shown beside it.
- `Band` always spans the same three whole levels, so extra easy levels do not inflate it.
- `≥` and `<` are bounds, not finite scores. Those rows are unranked.
- `†` is a finite estimate from a level with fewer than 3 valid tasks. Not ranked.
- `Official` rows use a direct provider and max effort. `Provisional` rows are exploratory.
- Effort levels are not the same test. Read the `Effort` column first.
- Official rows use 5 tasks at L1–L8 and 10 tasks at L9–L11.
- Half levels such as L9.5 are extra sizes between two whole levels. They sharpen `EQB-L` but do not count in `Band`. Every ranked row with a real gap at its bracket has one. L10.5 (n=27) went 3/5 for Astra high, 1/5 for Terra max and DeepSeek max, and 1/4 for Sol.

**What the data show**

Astra high and Sol form the top pair. Astra passed L10 5/5 and failed L11 0/5.
Sol passed L10 3/4 and failed L11 0/3. Their band rates are equal at 67%, so
`EQB-L` decides the order: Astra 10.59, Sol 10.25.

Terra max is third. It is the most reliable model below L10 (L9 10/10), but it
drops to 6/10 at L10, which pulls its band rate to 53%.

DeepSeek is the least reliable near the frontier. Its L10 rate is 5/10 at max
and 2/10 at high. At max effort its frontier (10.00) is close to Terra's (10.16),
but its band rate is 37% against 53%.

L11 (30×30) is still the wall. Astra, Sol, Terra, and DeepSeek all failed every
valid L11 task.

Gemini 4 Argon high reached L9 at 2/4, then the opencode-go 5-hour limit blocked
L10. It is a bound (`≥9.0`), not a score.

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
print(score.score)      # 4.94
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
  frontier_run.py    ladder runs and rebuilding a task bank from a receipt
  leaderboard.py     re-scores receipts and renders the published files
  generation/
    linear.py        dense integer systems, exact ground truth
  dataset.py         the task set a run answers, and its hash
  runner.py          concurrent, resumable provider runner
  scoring.py         run summaries: usage, cost, accuracy
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

1. Wire the adaptive staircase and the 5-task precision bank into the runner.
2. Run GPT-6.1 Sol and GPT-6 Astra at max effort on L10–L11 for a max-vs-max
   comparison. Astra is expensive, so use a hard budget cap.
3. Finish the Claude Haiku L8 bracket at an effort that does not hit the output
   cap.
4. Add the frontier curve, Pareto chart, and budget table to the site.
5. Replace provisional rows with clean direct-provider rows when routes and
   coverage pass the official rules.

See [`docs/polish-plan.md`](docs/polish-plan.md).

## The v1 archive

An earlier seven-track version (linear systems, polynomial expansion, recurrences
above 10^18, matrix-polynomial determinants, exponent towers, calculus) is
preserved at tag `v1-multitrack`. Different tasks, different score, not
comparable. It is kept because the numbers exist, not because they mean anything
today.

## License

MIT. See [LICENSE](LICENSE).
