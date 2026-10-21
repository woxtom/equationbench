# Reading the Leaderboard

The generated leaderboard lives in `leaderboard/index.html`. It is a static site with no external dependencies; open the file directly or serve it with any static server.

## Columns

| Column | Meaning |
|---|---|
| **#** | Rank within the selected division, by EQB Score |
| **Model** | Model name, lab, provider, and verification badges |
| **EQB Score** | Difficulty-weighted exact pass@1, 0–100, with a paired bootstrap 95% CI |
| **Accuracy** | Unweighted exact pass@1, with correct/total task count |
| **Track profile** | Seven small bars: one per track, height and color based on that track's EQB Score |
| **Cost / 100** | Provider-reported cost for 100 tasks; `free` means reported zero; `n/a` means the provider did not report cost |
| **Latency** | Median wall-clock latency, with p95 below |
| **↗** | Opens the model detail page with per-track/per-level breakdowns and sample answers |

## EQB Score

The primary metric weights each task by its difficulty level:

\[
\text{EQB Score} = 100 \cdot \frac{\sum_i \text{level}_i \cdot \mathbb{1}[\text{correct}_i]}{\sum_i \text{level}_i}
\]

It is exact pass@1, not a graded score. A wrong answer, timeout, refusal, provider error, missing prediction, or unparseable response counts as zero. There is no partial credit.

The score is not a percentage of “mathematical ability.” It is the fraction of available difficulty-weighted tasks a model solved exactly under the benchmark protocol.

## Confidence intervals and ranks

- Intervals are **paired cell-cluster bootstrap** 95% CIs over tasks, with 2,000 resamples by default. Family × level cells are resampled with replacement and all tasks in each chosen cell are kept. All models are evaluated on the same resampled cells.
- `rank_ci` in the data files gives the 2.5th–97.5th percentile of each model's rank across bootstrap replicates.
- `win_probability` is the fraction of replicates in which the model is rank 1.
- Overlapping intervals mean the data do not strongly distinguish two models at this sample size. The leaderboard shows intervals rather than declaring a single “winner” beyond the point estimate.
- The pairwise McNemar tests in `data/leaderboard.json` are diagnostic and are not corrected for multiple comparisons.

With 70 public tasks, the public leaderboard is a screening instrument. A one- or two-point difference is usually within noise. The sealed holdout (140 tasks) provides a larger confirmation set for top entries.

## Full set vs. preview

The **full** leaderboard scores all 70 public test tasks and runs with no per-task wall-clock timeout. Every ranked model has 70 predictions.

A **track subset** build (for example `--family linear`) scores only the selected family's tasks from the source runs. The site sets `n_tasks` to the subset size, shows `n_tasks_available`, and labels the build with its subset note. A 10-task subset has wide intervals; it is for cheap iteration, not fine-grained ranking.

The **preview** leaderboard scores the 35-task subset (one task per family × level cell) and used a 240-second timeout. Preview rows are labeled and are not directly comparable to full-set rows: tasks, timeout policy, and coverage differ. The full build is the reference ranking; the preview is retained so models whose providers were unavailable for the full sweep remain visible.

## Divisions

- **max** — the default division: one closed-book answer per task, no tools, highest requested reasoning effort (`max`), one attempt per task except transport retries. Full-set rows use no wall-clock timeout. Providers may clamp `max` to their highest supported level; the actual level is recorded.
- **standard/off** — archived full-set runs from the earlier protocol, which requested `off`.
- **open** — community/free models or other open configurations. They are ranked separately when `--include-preview` is used to build the site.
- **self-hosted** — local or self-hosted OpenAI-compatible endpoints.
- **extended** (future) — a higher, explicitly requested reasoning budget.

The site's division filter only shows divisions present in the current data. When only one division exists, the filter is hidden.

## Reasoning effort

Providers do not implement reasoning controls identically. The standard division requests `off`, but the actual level reported by the transport is recorded per run and shown on the model detail page. Examples:

- a provider may honor `off` literally;
- a provider may treat `off` as its minimum/low level;
- a provider may always run at `max` regardless of the request.

This is disclosed rather than hidden. The leaderboard is a comparison of models under their serving providers' behavior, not a controlled study of reasoning budgets. The run receipt records the requested and actual levels.

## Cost

Cost is the total provider-reported cost for the run, normalized to 100 tasks:

\[
\text{cost per 100} = \frac{\text{total cost}}{\text{number of evaluated tasks}} \cdot 100
\]

Costs are not comparable across providers with different pricing, free tiers, or subscription routing. The cost scatter is a practical efficiency view, not a claim about list price. Models with unavailable cost data are omitted from the scatter and shown as `n/a` in the table.

Latency is similarly provider-dependent: network queueing, batching, and rate limiting are included. The median is more robust than a single fast or slow call.

## Track profile

The seven bars in the table are EQB Scores for each track, not raw accuracies. A short bar can mean a model failed the hard tasks in that track even if it solved the easy ones. Hover a bar for the number. The model page shows both per-track score and per-level accuracy.

## Verification badges

- **verified** — official harness run with full coverage of the fixed public test set, committed artifacts, and a matching dataset hash.
- **preview** — partial coverage or a non-standard configuration; visible only when explicitly included.
- **open** — an open/community division row.
- **self-reported** / **sealed** — reserved for the submission workflow described in [submission.md](submission.md).

## Data files

The leaderboard directory ships machine-readable data:

- `data/leaderboard.json` — benchmark metadata, model rows, pairwise tests, per-task empirical difficulty, warnings.
- `data/leaderboard.csv` — flat model table for spreadsheets.
- `data/task_difficulty.csv` — per-task empirical accuracy across the included models.
- `data/runs.json` — included run ids, statuses, coverage, and thinking levels.
- `data/models/<slug>.json` — full model detail, including sample answers.

The site inlines a copy of the index data so it works from `file://`; the JSON files are the source of truth for programmatic use.

## Versioning and comparability

Rows are comparable only when they share:

- the same dataset hash (`benchmark.dataset_sha256`),
- the same dataset version (`v1`),
- the same scoring version,
- the same prompt version.

A model added after a dataset change belongs to a different benchmark season. The site displays the dataset version; the JSON includes generator and prompt versions. Do not compare scores across dataset versions.

## Common misreadings

- **“The model is 90% at math.”** No. It solved 90% of the difficulty-weighted tasks in this exact protocol, on this exact set, with no tools.
- **“Model A is better than Model B because it is one point higher.”** Check the intervals and the paired test before making that claim.
- **“The benchmark is saturated.”** A top score near 100 on the public set means the set is easy for that model, not that the model can solve arbitrary mathematics. The sealed holdout and future levels are designed to extend the range.
- **“Cost is price.”** Cost is the provider-reported amount for this run; free tiers, subscriptions, and routing can change it.
- **“Reasoning was held constant.”** The request was held constant. The actual level is provider-dependent and recorded.

For the full protocol, see [methodology.md](methodology.md). For task details, see [tasks.md](tasks.md).
