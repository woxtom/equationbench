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
