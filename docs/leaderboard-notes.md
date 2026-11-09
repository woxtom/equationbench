## How to read the table

- Ranked rows are sorted by `EQB-C` (`EQB-L × Band`). `EQB-L` is shown beside it.
- `Band` counts only the whole levels `floor(EQB-L) - 1` to `floor(EQB-L) + 1`. Easy levels below the frontier and half levels do not change it.
- `≥` and `<` are bounds, not finite scores. Those rows are unranked.
- `†` is a finite estimate from a level with fewer than 3 valid tasks. It is shown for reference only and is not ranked.
- `Official` rows use a direct provider and max effort. `Provisional` rows are exploratory.
- Effort levels are not the same test. Use the `Effort` column before you compare rows.
- Official rows use 5 tasks at L1-L8 and 10 tasks at L9-L11.
- Half levels such as L9.5 are extra sizes between two whole levels. They sharpen `EQB-L` but do not count in `Band`. Every ranked row with a real gap at its bracket has one. L10.5 (n=27) went 3/5 for Astra high, 1/5 for Terra max and DeepSeek max, and 1/4 for Sol.
- DeepSeek high uses 10 tasks at L10-L11. The other high rows use 5 core tasks.
- GPT-6.1 Sol high has exactly 90% valid coverage (4 timeouts), the minimum for a ranked row.
- GPT-6.1 Sol high uses the core 5-task row. Its 10-task precision extension had 7 timeouts and 84% valid completion.
- `*` means the cost excludes at least one timed-out call with no cost record.

## What the data show

Astra high and Sol form the top pair. Astra reached L10 5/5 and failed L11 0/5; Sol passed L10 3/4 and failed L11 0/3. Their band rates are equal (67%), so EQB-L decides the order: Astra 10.59, Sol 10.25.

Terra max is third. It is more reliable below L10 (L9 10/10) but weaker at L10 (6/10), which pulls its band rate to 53%.

DeepSeek is the least reliable of the four near the frontier. Its L10 rate is 5/10 at max and 2/10 at high. At max effort its frontier (10.00) is close to Terra's (10.16), but its band rate is 37% against 53%.

L11 (30x30) is still the wall. Astra, Sol, Terra, and DeepSeek all failed every valid L11 task. No model cleared L11.

Gemini 4 Argon high reached L9 at 2/4 and then the opencode-go 5-hour limit blocked L10. It is reported as a bound (>=9.0), not a score.

## Caveats

- OpenAI lists `gpt-6.1-sol` and `gpt-6.1-terra`, but no `gpt-6.1-luna`. The Luna row uses `gpt-6-luna`.
- High-effort rows start at L5 (strong models) or L3 (weaker models). The score needs only the levels around the bracket.
- `Band` jumps when `EQB-L` crosses a whole number, because the three-level window moves. Treat small EQB-C differences near a whole-number score as noise.
- A degenerate CI (equal low and high ends) means every task at the bracket levels passed or failed. The task bootstrap cannot show variance in that case.
- The stale 2026-10 batch probes are not used in the ranked rows.
