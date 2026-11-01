# EquationBench Linear Leaderboard

Generated: `2026-11-01T03:06:17+00:00`

Season seed `731992` · ladder v1 · scoring v2. One table, all runs.

Web view: <https://woxtom.github.io/equationbench/>

`EQB-C = EQB-L × Band` is the ranked composite. It rewards a high frontier and reliability near that frontier. `EQB-L` is the 50% frontier. `Band` is the exact-solve rate over the tested levels in `[EQB-L - 2, EQB-L + 1]`: the window around the frontier. That window is fixed in width, so testing extra easy or hard levels does not move it. `Solved` is exact answers divided by all tasks. `Cover` is valid tasks divided by all tasks. Provider errors are excluded from the rate, but they lower the coverage.

| # | Model | Effort | Status | EQB-C | EQB-L (95% CI) | Solved | Band | Cover | Cost | Note |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | [GPT-6 Astra](runs/provisional/2026-10/astra/openai-gpt-6-astra-high) | high | Provisional | 7.00 | 10.50 (10.50–10.50) | 15/20 | 67% (L9–L11) | 100% | $16.79 | CI is degenerate: every bracket-level task passed or failed, so the task bootstrap has no variance |
| 2 | [GPT-6.1 Sol](runs/provisional/2026-10/high/openai-gpt-6-1-sol-core5) | high | Provisional | 6.89 | 10.33 (9.67–10.50) | 28/35 | 67% (L9–L11) | 91% | $3.87* | 3 provider timeout(s) |
| 3 | [GPT-6.1 Terra](runs/official/2026-10/openai-gpt-6-1-terra) | max | Official | 5.42 | 10.17 (9.71–10.44) | 56/70 | 53% (L9–L11) | 100% | $5.73 |  |
| 4 | [DeepSeek V4.1 Flash](runs/provisional/2026-10/high/deepseek-v4-1-flash) | high | Provisional | 4.75 | 9.50 (8.62–10.00) | 25/45 | 50% (L8–L10) | 100% | $4.18 |  |
| 5 | [DeepSeek V4.1 Flash](runs/official/2026-10/deepseek-v4-1-flash) | max | Official | 4.57 | 10.00 (8.83–10.33) | 51/70 | 46% (L8–L11) | 100% | $7.62 |  |
| 6 | [GPT-6 Astra](runs/provisional/2026-10/astra/openai-gpt-6-astra-medium) | medium | Provisional | 3.82 | 7.17 (6.62–7.50) | 13/35 | 53% (L6–L8) | 100% | $3.93 |  |
| 7 | [GPT-6 Astra](runs/provisional/2026-10/astra/openai-gpt-6-astra-low) | low | Provisional | 3.29 | 6.17 (5.62–6.50) | 8/35 | 53% (L5–L7) | 100% | $2.62 |  |
| 8 | [GPT-6.1 Terra](runs/provisional/2026-10/high/openai-gpt-6-1-terra) | high | Provisional | 3.00 | 4.50 (3.83–5.17) | 10/20 | 67% (L3–L5) | 100% | $0.11 |  |
| 9 | [GPT-6 Luna](runs/provisional/2026-10/high/openai-gpt-6-luna) | high | Provisional | 2.25 | 3.75 (3.25–4.38) | 6/20 | 60% (L3–L4) | 100% | $0.04 |  |
| 10 | [GLM-5.3 Flash](runs/provisional/2026-10/high/zai-glm-5-3-flash) | high | Provisional | 2.17 | 3.62 (3.50–4.17) | 6/20 | 60% (L3–L4) | 100% | $0.30 |  |
| — | [Claude Haiku 5.5](runs/provisional/2026-10/high/anthropic-claude-haiku-5-5) | high | Unranked | — | ≥8.0 | 16/20 | — | 80% | $0.77* | 4 response(s) hit the output token cap |
| — | [GPT-5.6 Luna](runs/provisional/2026-10/openai-gpt-5-6-luna) | max | Unranked | — | ≥8.0 | 36/55 | — | 65% | unknown | 7 response(s) hit the output token cap |
| — | [Gemini 4 Argon](runs/provisional/2026-10/gemini/google-gemini-4-argon-high) | high | Unranked | — | ≥9.0 | 7/15 | 78% (L8–L9) | 60% | $5.16* | cost excludes 3 call(s) with no cost record |
| — | [MiMo v2.6 Flash](runs/provisional/2026-10/high/xiaomi-mimo-v2-6-flash) | high | Unranked | — | ≥5.0 | 13/20 | — | 65% | unknown | 2 provider timeout(s) |

## How to read the table

- Ranked rows are sorted by `EQB-C` (`EQB-L × Band`). `EQB-L` is shown beside it.
- `Band` counts only the tested levels in `[EQB-L - 2, EQB-L + 1]`. Easy levels below the frontier do not inflate it.
- `≥` and `<` are bounds, not finite scores. Those rows are unranked.
- `†` is a finite estimate from a level with fewer than 3 valid tasks. It is shown for reference only and is not ranked.
- `Official` rows use a direct provider and max effort. `Provisional` rows are exploratory.
- Effort levels are not the same test. Use the `Effort` column before you compare rows.
- Official rows use 5 tasks at L1-L8 and 10 tasks at L9-L11.
- DeepSeek high uses 10 tasks at L10-L11. The other high rows use 5 core tasks.
- GPT-6.1 Sol high uses the core 5-task row. Its 10-task precision extension had 7 timeouts and 84% valid completion.
- `*` means the cost excludes at least one timed-out call with no cost record.

## What the data show

Astra high and Sol form the top pair. Astra reached L10 5/5 and failed L11 0/5; Sol passed L10 3/4 and failed L11 0/3. Their band rates are equal (67%), so EQB-L decides the order: Astra 10.50, Sol 10.33.

Terra max is third. It is more reliable below L10 (L9 10/10) but weaker at L10 (6/10), which pulls its band rate to 53%.

DeepSeek is the least reliable of the four near the frontier. Its L10 rate is 5/10 at max and 2/10 at high. Its frontier is the same as Terra's, but its band rate is 9 to 16 points lower.

L11 (30x30) is still the wall. Astra, Sol, Terra, and DeepSeek all failed every valid L11 task. No model cleared L11.

Gemini 4 Argon high reached L9 at 2/4 and then the opencode-go 5-hour limit blocked L10. It is reported as a bound (>=9.0), not a score.

## Caveats

- OpenAI lists `gpt-6.1-sol` and `gpt-6.1-terra`, but no `gpt-6.1-luna`. The Luna row uses `gpt-6-luna`.
- High-effort rows start at L5 (strong models) or L3 (weaker models). The score needs only the levels around the bracket.
- `Band` uses a fixed window around each frontier. A run that stops at a different level can shift the band by a few points, so treat EQB-C differences under 0.5 as noise.
- A degenerate CI (for example 10.50-10.50) means every task at the bracket levels passed or failed. The task bootstrap cannot show variance in that case.
- The stale 2026-10 batch probes are not used in the ranked rows.

