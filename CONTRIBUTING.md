# Contributing to EquationBench

EquationBench is a benchmark, so changes to the ladder, prompt, parser, or
scoring are changes to the measurement instrument. Open an issue before changing
any of those.

The benchmark is intentionally one track: dense linear systems. New task families
are out of scope. Improvements to the ladder protocol, stability, cost reporting,
and the site are welcome.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run eqb ladder --max-level 20
```

## Changing the ladder or score

- Ladder changes bump `LADDER_VERSION` and `GENERATOR_VERSION`.
- Prompt changes bump `PROMPT_VERSION`.
- Parser or scoring changes bump `SCORING_VERSION`.
- A new season rotates the public seed and freezes a new task bank.
- Rows are comparable only within the same ladder/prompt/scoring/season versions
  and shared horizon. Current EQB scoring is specified in `docs/ladder.md`.

Do not silently change the coefficient bound, solution bound, task count, or the
shared scoring grid, horizon, integration scale, or missing-level policy.

## Adding a model

1. Add a `[[models]]` entry to `config/models.toml`.
2. Prefer a direct, versioned provider API. Disclose the route.
3. Run the pilot and the official protocol.
4. Validate the artifacts and open a pull request as described in
   [`docs/submission.md`](docs/submission.md).

A leaderboard with five clean rows is stronger than twenty unstable ones. Models
with a high provider-error rate or a silent version change are not eligible.

## Data hygiene

- Do not edit predictions or omit failed tasks.
- Never hand-edit generated leaderboard values. Run `eqb build-leaderboard`,
  commit its outputs with scoring changes, and verify with `--check`.
- Preserve historical receipts and raw predictions; do not relabel old frontier
  summaries as v3 EQB.

## Code style

- Python 3.11+.
- Exact integer arithmetic for ground truth; never floats.
- Keep the generator deterministic and bounded.
- Prefer small, auditable functions.
- Add tests for every non-trivial scoring or parser behavior.

## Reporting issues

Include the ladder version, scoring version, task id, model key, run id, and the
raw response if the issue is about parsing. Corrections to an answer need an
independent exact computation.
