# Runs

- `official/` — clean, ranked rows on a frozen ladder season.
- `provisional/` — exploratory rows (high, low, medium, or max effort).
- `pilot/` — early ladder and frontier-scorer validation.
- `logs/` — local batch stdout (git-ignored). File names use `__` for the path separator.
- `_archive/` — superseded probes. Kept for the record; not scored.

A run directory contains `run.json`, `predictions.jsonl`, `summary.json`, and
`frontier.json`.

Provider errors and timeouts are infrastructure failures, not model answers.
They are excluded from the frontier denominator and they lower the completion
rate. A run with too few valid tasks is not ranked.

Do not compare a `pilot/` or `_archive/` row to a ranked row without checking
ladder version, task set, effort, and coverage.
