# Reading the Leaderboard

**Status:** the v2 frontier leaderboard is not published yet. The scoring core
and ladder are implemented; the staircase runner and site are the next step.
This page describes the intended presentation.

## Primary column: EQB-L

`EQB-L` is the continuous ladder level at which the model has a 50% chance of
solving an exact system. It is not a percentage and it has no fixed ceiling.

Examples:

- `EQB-L 9.5` means the model is at 50% around a 21×21 system.
- `EQB-L 12.8` means the model is at 50% around a 43×43 system.

The table also shows the physical frontier size \(n^*\), the bootstrap 95%
interval, and whether the row is censored.

## Censoring

A model that passes every attempted level is reported as `≥ Lmax`, not as a fake
finite score. Extend the ladder until it fails. A model that fails L1 is reported
below L1. Never compare a censored row to a finite row as if the bound were a
measurement.

## Capability and cost

The site shows two axes:

- **Frontier curve:** success probability vs. ladder level, with the `L*` marker.
- **Cost frontier:** `EQB-L` vs. cost to frontier. Non-dominated models are
  highlighted.

Useful filters:

- **Best under budget:** highest frontier for $1, $5, $20, or $100.
- **Cheapest within Δ:** cheapest model that reaches L8, L10, or L12.
- **Stability:** completion rate, provider-error rate, and repeat agreement.

Cost is provider-reported and labeled with a basis (`api_list`,
`subscription_amortized`, `free`, `unknown`). Do not compare across bases without
reading the label.

## Confidence intervals

Intervals are task-level bootstrap estimates within each level, with the same
resampled tasks used across models. A 5-task-per-level run is noisy; the protocol
adds 5 precision tasks at the two bracket levels before stopping.

## What the leaderboard is not

- It is not a general math ability score.
- It is not a ranking of tool-assisted systems.
- It does not claim that a 0.5-level difference is meaningful; check the interval.
- It does not mix reasoning efforts or provider bases in one official rank.

## Data files

The eventual site will ship machine-readable data:

- `data/leaderboard.json` — models, frontier scores, intervals, warnings.
- `data/leaderboard.csv` — flat table.
- `data/models/<slug>.json` — per-level outcomes and sample failures.
- `data/runs.json` — run ids, provider/route, reasoning level, cost basis.

The v1 leaderboards are preserved in the `v1-multitrack` git tag and are not
comparable to v2.
