# EquationBench Linear

**How large a linear system can a model solve exactly—and how reliably?**

Every task is a dense integer linear system with a unique solution. One prompt,
no tools, exact answers. The single score, **EQB**, integrates success across
difficulty: reach and reliability in one number.

> **Unofficial.** Not peer-reviewed, not an official evaluation, and not a
> measure of general mathematical ability. Every row links to a run receipt
> that can be regenerated from the published seed.
>
> **Site:** <https://woxtom.github.io/equationbench/>
>
> **Status:** scoring v3.0 is implemented. The published leaderboard uses a
> shared L1–L11 scoring grid. The ladder can extend beyond it; extending the
> comparison horizon requires a shared protocol update. Adaptive runs are not
> wired yet.

## The task and ladder

Given `A` and `b = A·x`, return the integer vector `x`:

```json
{"answer": [3, -1, 7]}
```

Exact comparison after canonicalization. No judge, tolerance, or partial credit.
Coefficients stay in `[-30, 30]` and solutions in `[-9, 9]`. Size is the only
difficulty axis:

$$
n_L = \mathrm{round}\left(3 \cdot 2^{(L-1)/3}\right).
$$

| L | n | L | n | L | n | L | n |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 6 | 10 | 11 | 30 | 16 | 96 |
| 2 | 4 | 7 | 12 | 12 | 38 | 17 | 121 |
| 3 | 5 | 8 | 15 | 13 | 48 | 18 | 152 |
| 4 | 6 | 9 | 19 | 14 | 60 | 19 | 192 |
| 5 | 8 | 10 | 24 | 15 | 76 | 20 | 242 |

Three ideal levels double the size. The ladder has no permanent ceiling.

## One score: effective solved levels

Fit a non-increasing isotonic success curve to valid outcomes at whole levels.
Interpolate in actual log system size, using
`x_L = 1 + 3 log2(n_L / 3)`, then integrate through the shared horizon:

$$
\boxed{\mathrm{EQB} = 1 + \int_1^{x_H} \hat p(x)\,dx}
$$

For this season, `H = 11` (30 variables, `x_H ≈ 10.9658`).

- **Reach:** success on harder systems extends the area.
- **Reliability:** mistakes on easier systems reduce it.
- **No moving window:** better outcomes cannot lower EQB on a fixed grid with
  fixed trial counts.
- **No dilution:** the area is not divided by task count or number of levels.
  Extending an all-zero tail leaves it unchanged.
- **One comparable grid:** whole levels only. Half levels remain diagnostics;
  extra trials refine rates without directly increasing a level's area weight.

One unit of difficulty solved with 60% probability contributes 0.6 points.
The initial 1 is a coordinate offset. EQB is not a percentage or a frontier
system size. At a fixed horizon it has a ceiling; extending that horizon is a
versioned change applied to every row together.

Missing grid points are bounded by monotonicity. If their rates are not
identified, the row shows **bounds**, not a ranked point score. Fitted 100%/0%
plateaus can identify untested easy/hard regions under the empirical model;
these assumptions are disclosed. They are not observed successes or failures.

The old frontier multiplier and moving band are retired. See
[`docs/ladder.md`](docs/ladder.md) for the formula, missing-level rules,
bootstrap limitations, and migration details.

## Leaderboard (2026-10)

Season seed `731992` · ladder v1 · scoring v3.0 · shared horizon L11.

Ranked by **EQB** alone. Parentheses show a task-bootstrap 95% interval.
`[bounds]` denotes an unresolved-region range, **not** a confidence interval.
`Solved` counts exact answers over all tasks; `Cover` counts valid responses
over all tasks. Cost and tokens do not affect rank.

<!-- leaderboard:start -->
| # | Model | Effort | Status | EQB (95% CI) | Solved | Cover | Tokens | Cost | Note |
|---:|---|---|---|---:|---:|---:|---:|---:|---|
| 1 | [GPT-6 Astra](runs/provisional/2026-10/astra/openai-gpt-6-astra-high) | high | Provisional | 10.48 (10.48–10.48) | 18/25 | 100% | 515k | $22.70 | CI is degenerate: every scoring-level task passed or failed, so the task bootstrap has no variance; monotone plateau inferred at levels [1, 2, 3, 4, 5, 6, 7] |
| 2 | [GPT-6.1 Sol](runs/provisional/2026-10/high/openai-gpt-6-1-sol-core5) | high | Provisional | 10.24 (9.74–10.48) | 29/40 | 90% | 567k | $5.06* | 4 provider timeout(s); monotone plateau inferred at levels [1, 2, 3, 4]; cost excludes 4 call(s) with no cost record |
| 3 | [GPT-6.1 Terra](runs/official/2026-10/openai-gpt-6-1-terra) | max | Official | 10.09 (9.79–10.38) | 57/75 | 100% | 1.41M | $6.45 |  |
| 4 | [DeepSeek V4.1 Flash](runs/official/2026-10/deepseek-v4-1-flash) | max | Official | 9.58 (9.18–9.99) | 52/75 | 100% | 7.54M | $8.91 |  |
| 5 | [DeepSeek V4.1 Flash](runs/provisional/2026-10/high/deepseek-v4-1-flash) | high | Provisional | 9.29 (8.69–9.79) | 27/50 | 100% | 4.49M | $5.28 | monotone plateau inferred at levels [1, 2, 3, 4] |
| 6 | [GPT-6 Astra](runs/provisional/2026-10/astra/openai-gpt-6-astra-medium) | medium | Provisional | 7.13 (6.78–7.48) | 18/40 | 100% | 178k | $5.98 | monotone plateau inferred at levels [1, 2, 3, 4] |
| 7 | [GPT-6 Astra](runs/provisional/2026-10/astra/openai-gpt-6-astra-low) | low | Provisional | 6.25 (5.90–6.61) | 12/40 | 100% | 131k | $3.69 | monotone plateau inferred at levels [1, 2, 3, 4] |
| 8 | [GPT-6.1 Terra](runs/provisional/2026-10/high/openai-gpt-6-1-terra) | high | Provisional | 4.64 (4.22–5.08) | 10/25 | 100% | 43k | $0.16 | monotone plateau inferred at levels [1, 2, 7, 8, 9, 10, 11] |
| 9 | [GLM-5.3 Flash](runs/provisional/2026-10/high/zai-glm-5-3-flash) | high | Provisional | 3.81 (3.61–4.22) | 6/20 | 100% | 599k | $0.30 | monotone plateau inferred at levels [1, 2, 7, 8, 9, 10, 11] |
| — | [Claude Haiku 5.5 (OpenRouter)](runs/provisional/2026-10/openrouter/anthropic-claude-haiku-5-5-high) | high | Unranked | 7.98–9.22 [bounds] | 11/30 | 40% | 1.74M | unknown | 5 response(s) hit the output token cap; EQB bounds only: unresolved levels [9, 10, 11]; monotone plateau inferred at levels [1, 2, 3, 4, 5] |
| — | [GPT-5.6 Luna](runs/provisional/2026-10/openai-gpt-5-6-luna) | max | Unranked | 8.48–10.97 [bounds] | 36/55 | 65% | 2.15M | unknown | 7 response(s) hit the output token cap; EQB bounds only: unresolved levels [9, 10, 11] |
| — | [GPT-6 Luna](runs/provisional/2026-10/high/openai-gpt-6-luna) | high | Unranked | 3.49–3.84 [bounds] | 6/20 | 100% | 86k | $0.04 | EQB bounds only: unresolved levels [1, 2]; monotone plateau inferred at levels [7, 8, 9, 10, 11] |
| — | [Gemini 4 Argon](runs/provisional/2026-10/gemini/google-gemini-4-argon-high) | high | Unranked | 8.99–9.72 [bounds] | 7/15 | 60% | 533k | $5.16* | EQB bounds only: unresolved levels [10, 11]; monotone plateau inferred at levels [1, 2, 3, 4, 5, 6, 7]; cost excludes 3 call(s) with no cost record |
| — | [MiMo v2.6 Flash](runs/provisional/2026-10/high/xiaomi-mimo-v2-6-flash) | high | Unranked | 5.73–10.97 [bounds] | 13/20 | 65% | 573k | unknown | 2 provider timeout(s); EQB bounds only: unresolved levels [6, 7, 8, 9, 10, 11]; monotone plateau inferred at levels [1, 2] |
<!-- leaderboard:end -->

**How to read it**

- Official rows use a direct provider at max effort with complete valid coverage.
  Provisional rows are exploratory and require at least 90% valid coverage.
- A finite estimate marked `†` fails the ranking rules. Bounds-only rows are unranked.
- Effort settings and routes differ; a higher setting is not guaranteed to win.
- Notes disclose inferred plateaus. New runs should measure the full scoring grid.
- The bootstrap resamples whole-level tasks and recomputes the entire area.
  Small all-pass/all-fail banks can understate uncertainty. A close point ranking
  is not a demonstrated pairwise win.
- Total run cost depends on the task set, including diagnostic tasks.

**What changed**

DeepSeek max now ranks above high because of its integrated performance, not
an effort bonus. GPT-6 Luna high is unranked until its untested easy levels are
resolved. Values differ slightly from the exploratory area preview because the
published score uses a common whole-level grid, not selectively sampled half levels.

## Quick start

Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
uv run eqb ladder --max-level 20
uv run eqb ladder --max-level 10 --measure
uv run eqb run-ladder --model deepseek-v4-1-flash --levels 1-11 --dry-run
uv run eqb build-leaderboard
uv run eqb build-leaderboard --check
```

Score counts without calling a model:

```python
from equationbench.area import estimate_from_counts

result = estimate_from_counts({
    1: (5, 5), 2: (5, 5), 3: (5, 5),
    4: (4, 5), 5: (2, 5), 6: (0, 5),
})
print(result.score)             # EQB effective solved levels
print(result.ci)                # task-bootstrap 95% interval
print(result.bounds)            # identification bounds; equal for a point estimate
print(result.inferred_levels)   # untested plateau knots, explicitly disclosed
```

Regenerate a task:

```python
from equationbench.ladder import build_ladder_task

task = build_ladder_task(level=10, index=0)
print(task.metadata["n"], len(task.prompt), task.answer_type)
```

## Receipts and repository layout

Every row must retain raw responses, task IDs, seed/version tuple, dataset hash,
provider/route/effort, usage, latency, cost, and infrastructure failures.
Timeouts are not wrong answers; missing coverage remains visible.

```text
src/equationbench/
  ladder.py          deterministic geometric ladder
  area.py            EQB area, missing-grid bounds, bootstrap
  ladder_run.py      run fixed ladder sets; rebuild receipts
  leaderboard.py     re-score receipts and render published files
  frontier.py        legacy v2 estimator, historical reproduction only
  frontier_run.py    compatibility imports for pre-v3 scripts
  scoring.py         accuracy, usage, cost, and latency summaries
  generation/linear.py
  verify.py          exact answer parser and grader
config/models.toml   model registry
data/leaderboard.*   generated current results
docs/ladder.md       scoring and protocol specification
docs/submission.md   how to submit a run
tests/              generator, scorer, parser, runner, CLI, and leaderboard tests
```

New runs write `eqb.json` and `summary.json["eqb"]`. Historical receipts,
including old `frontier.json` files, are preserved. Published scores are always
rebuilt from predictions; old scores are not relabeled as EQB.

## Next steps

1. Fill unresolved grid coverage, especially GPT-6 Luna's easier levels.
2. Collect standardized full-grid, max-effort comparisons.
3. Add predeclared precision sampling and a sealed holdout.
4. Extend the shared horizon when models show meaningful success at its top.

## Archives

The earlier seven-track benchmark is preserved at tag `v1-multitrack`.
The v2 frontier estimator and original receipt artifacts remain reproducible,
but their scores are not comparable to v3 EQB.
[`docs/polish-plan.md`](docs/polish-plan.md) is an archived v2 design plan,
not the current scoring specification.

## License

MIT. See [LICENSE](LICENSE).
