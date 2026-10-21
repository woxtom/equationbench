# Runs

- `pilot/` — exploratory runs used to validate the ladder and frontier scorer.
- `official/` — clean, ranked rows on a frozen ladder season.

A run directory contains `run.json`, `predictions.jsonl`, `summary.json`, and
`frontier.json`. Provider errors are infrastructure failures, not model answers;
they are excluded from the frontier denominator and reduce the completion rate.

Pilot rows are not official and should not be compared to a future official
leaderboard without checking the ladder version, task set, and reasoning level.
