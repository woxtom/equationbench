# EquationBench Linear Leaderboard

Generated: `2026-11-09T08:03:18+00:00`

Season seed `731992` · ladder v1 · scoring v3.0. One table, all runs.

Web view: <https://woxtom.github.io/equationbench/>

`EQB` is effective solved levels: 1 plus area under the isotonic success curve on the shared whole-level grid, through L11. Higher is better. Interpolation uses log system size. Ranges marked [bounds] reflect unresolved levels, not confidence intervals, and are unranked. `Solved` is exact answers over all tasks; `Cover` is valid answers over all tasks. Provider errors lower coverage, not per-level accuracy.

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

## How to read the table

- Ranked rows are sorted by **EQB effective solved levels** alone, with a task-bootstrap 95% interval. No frontier multiplier, moving band, or cost bonus.
- Scoring v3.0 integrates the isotonic success curve on whole levels L1–L11 in actual log-size coordinates. Half levels remain diagnostics and count toward run cost/coverage, not EQB.
- Ranges marked `[bounds]` reflect unresolved grid regions, conditional on fitted rates. They are not confidence intervals and are unranked.
- `†` marks a finite estimate that fails another ranking rule.
- Notes list untested levels inferred from equal-rate monotone plateaus. A 100% first fitted rate or a zero last fitted rate can identify a missing easy prefix or hard suffix under this model; it is not proof about true probabilities.
- `Official` rows use a direct provider at max effort and 100% valid coverage. `Provisional` rows require at least 90%. Every observed scoring level needs at least 3 valid trials.
- Effort levels and routes differ. Do not treat point-estimate order as proof of a pairwise win.
- `Solved` is exact answers divided by all tasks; `Cover` is valid responses divided by all tasks. Infrastructure failures are excluded from per-level rate estimates.
- `*` on cost means at least one call had no cost record. Whole-run cost/token comparisons depend on task coverage.

## What changed in v3

DeepSeek max ranks above high on integrated performance. There is no effort bonus:
both use the same difficulty weights, and neither receives an easier scoring window.

The exploratory area preview included selectively sampled half levels. Published
v3 scores use the common whole-level grid instead, so some values differ slightly.

GPT-6 Luna high begins at L3 with 4/5 correct. Its missing L1–L2 rates are not
identified; it now shows bounds rather than an invented ranked score. Other
incomplete provider-limited runs remain unranked.

The shared horizon is L11 (30×30). Every valid L11 response in the current top
rows was wrong. Extending the horizon is a shared protocol update, never a
per-model scoring choice.

## Caveats

- Bootstrap intervals are conditional on the fitted curve and grid. At all-pass/all-fail levels, resampling cannot express unobserved failures/successes; small banks can understate uncertainty even when the overall CI is not degenerate.
- Official legacy runs have 5 tasks at L1–L8 and 10 at L9–L11. Other rows have different precision allocations. Trial counts refine estimates rather than directly weight the integrated area.
- GPT-6.1 Sol high uses the core 5-task receipt: 90% valid coverage and 4 timeouts. Its larger precision extension had 84% valid coverage and is not used for ranking.
- Historical receipt summaries and `frontier.json` files retain their original versions. This table is recomputed from predictions with scoring v3.0; old frontier and composite values are not comparable.
- The adaptive runner and sealed holdout are not implemented. New runs should measure the full common grid with a predeclared precision plan.
- The stale batch probes are not used in ranked rows.
