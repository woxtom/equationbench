# EquationBench Linear Leaderboard

Generated: `2026-11-09T06:51:54+00:00`

Season seed `731992` · ladder v1 · scoring v2.2. One table, all runs.

Web view: <https://woxtom.github.io/equationbench/>

`EQB-C = EQB-L × Band` is the ranked composite. It rewards a high frontier and reliability near that frontier. `EQB-L` is the 50% frontier. `Band` is the exact-solve rate over the whole levels `floor(EQB-L) - 1` to `floor(EQB-L) + 1`. Testing extra easy or hard levels does not move that window. `Solved` is exact answers divided by all tasks. `Cover` is valid tasks divided by all tasks. Provider errors are excluded from the rate, but they lower the coverage.

| # | Model | Effort | Status | EQB-C | EQB-L (95% CI) | Solved | Band | Cover | Tokens | Cost | Note |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | [GPT-6 Astra](runs/provisional/2026-10/astra/openai-gpt-6-astra-high) | high | Provisional | 6.99 | 10.48 (10.48–10.48) | 15/20 | 67% (L9–L11) | 100% | 382k | $16.79 | CI is degenerate: every bracket-level task passed or failed, so the task bootstrap has no variance |
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

## How to read the table

- Ranked rows are sorted by `EQB-C` (`EQB-L × Band`). `EQB-L` is shown beside it.
- `Band` counts only the whole levels `floor(EQB-L) - 1` to `floor(EQB-L) + 1`. Easy levels below the frontier and half levels do not change it.
- `≥` and `<` are bounds, not finite scores. Those rows are unranked.
- `†` is a finite estimate from a level with fewer than 3 valid tasks. It is shown for reference only and is not ranked.
- `Official` rows use a direct provider and max effort. `Provisional` rows are exploratory.
- Effort levels are not the same test. Use the `Effort` column before you compare rows.
- Official rows use 5 tasks at L1-L8 and 10 tasks at L9-L11.
- Half levels such as L9.5 are extra sizes between two whole levels. They sharpen `EQB-L` but do not count in `Band`. Every ranked row with a real gap at its bracket has one, except Astra high. L10.5 (n=27) went 1/5 for Terra max and DeepSeek max, and 1/4 for Sol.
- DeepSeek high uses 10 tasks at L10-L11. The other high rows use 5 core tasks.
- GPT-6.1 Sol high has exactly 90% valid coverage (4 timeouts), the minimum for a ranked row.
- GPT-6.1 Sol high uses the core 5-task row. Its 10-task precision extension had 7 timeouts and 84% valid completion.
- `*` means the cost excludes at least one timed-out call with no cost record.

## What the data show

Astra high and Sol form the top pair. Astra reached L10 5/5 and failed L11 0/5; Sol passed L10 3/4 and failed L11 0/3. Their band rates are equal (67%), so EQB-L decides the order: Astra 10.48, Sol 10.25.

Terra max is third. It is more reliable below L10 (L9 10/10) but weaker at L10 (6/10), which pulls its band rate to 53%.

DeepSeek is the least reliable of the four near the frontier. Its L10 rate is 5/10 at max and 2/10 at high. At max effort its frontier (10.00) is close to Terra's (10.16), but its band rate is 37% against 53%.

L11 (30x30) is still the wall. Astra, Sol, Terra, and DeepSeek all failed every valid L11 task. No model cleared L11.

Gemini 4 Argon high reached L9 at 2/4 and then the opencode-go 5-hour limit blocked L10. It is reported as a bound (>=9.0), not a score.

## Caveats

- OpenAI lists `gpt-6.1-sol` and `gpt-6.1-terra`, but no `gpt-6.1-luna`. The Luna row uses `gpt-6-luna`.
- High-effort rows start at L5 (strong models) or L3 (weaker models). The score needs only the levels around the bracket.
- `Band` jumps when `EQB-L` crosses a whole number, because the three-level window moves. Treat small EQB-C differences near a whole-number score as noise.
- A degenerate CI (for example 10.48-10.48) means every task at the bracket levels passed or failed. The task bootstrap cannot show variance in that case.
- The stale 2026-10 batch probes are not used in the ranked rows.
