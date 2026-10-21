# EquationBench Linear v2 — Polish Plan

**Decision:** drop the other six tracks. Make EquationBench a **linear-systems-only**
benchmark with an **open-ended geometric difficulty ladder** and a **frontier score**
that has no ceiling. Use a small slate of cheap, stable, directly-served models.

This is a stronger product than the seven-track version:

- one clean difficulty axis (system size),
- one number that can grow forever (the 50% frontier),
- much less code and surface area,
- cheaper runs, because weak models stop early,
- an obvious visual: success probability vs. system size.

The multi-track code and artifacts were removed from `main` in the cleanup pass and
preserved in the `v1-multitrack` git tag. They are not comparable to v2.

## Implementation status

Done in the first implementation pass:

- `src/equationbench/ladder.py`: geometric `size_for_level(L)`, deterministic
  `build_ladder_task`, core/precision bank helpers, prompt-size estimates, and a
  machine-readable manifest.
- `src/equationbench/frontier.py`: isotonic smoothing, 50% bracket interpolation,
  censoring, deterministic task-level bootstrap CIs, and count/outcome wrappers.
- `eqb ladder`: prints L1–L20 with size, estimated prompt tokens, task counts, and
  the core/extension split; `--measure` generates one real task per level;
  `--json` emits the manifest.
- `tests/test_ladder.py`, `tests/test_frontier.py`, and CLI coverage for `eqb ladder`.
- Repository cleanup: the six other tracks, generated leaderboards, stale runs,
  old datasets, one-off scripts, server/db code, and caches were removed; the
  package is linear-only; secrets now live outside the repo.
- CI workflow, short README, linear-only docs, and a pilot model slate.

Still to do: wire the frontier score into `runner.py`/`leaderboard.py`, materialize
ladder runs, and replace the multi-track site.

---

## 1. The ladder: `L1` to `L∞`

Every level is a system size \(n\). The ladder is geometric, so each level is a
constant multiplicative step in size:

\[
n_L = \operatorname{round}\!\left(3 \cdot 2^{(L-1)/3}\right), \qquad L=1,2,3,\dots
\]

| L | n | L | n | L | n | L | n |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 6 | 10 | 11 | 30 | 16 | 96 |
| 2 | 4 | 7 | 12 | 12 | 38 | 17 | 121 |
| 3 | 5 | 8 | 15 | 13 | 48 | 18 | 152 |
| 4 | 6 | 9 | 19 | 14 | 60 | 19 | 192 |
| 5 | 8 | 10 | 24 | 15 | 76 | 20 | 242 |

Each three levels doubles \(n\), so each level is roughly a 26% size increase and a
~2× increase in elimination work. Equal \(L\) steps are equal steps in \(\log n\),
which is the natural difficulty scale for a dense linear system.

**Fixed parameters:** dense integer coefficients in \([-30,30]\), solution entries in
\([-9,9]\), unique solution. Do not scale the coefficient bound; \(n\) is the only
difficulty axis. This keeps the score interpretable and the generator auditable.

**Practical range:** \(L20\) is a 242×242 system. Estimated prompt size grows as
\(O(n^2)\):

| n | prompt chars (approx) | prompt tokens (approx) |
|---:|---:|---:|
| 24 | 5.2k | 1.3k |
| 38 | 12k | 3k |
| 64 | 34k | 9k |
| 96 | 76k | 19k |
| 128 | 138k | 35k |
| 192 | 321k | 80k |

So the ladder is limited by context and cost, not by generation. Publish a token
estimate per level and cap the official protocol at a level every included model can
attempt (e.g. `L17`, 121×121, ~31k prompt tokens). Extension levels remain available
for long-context models or later seasons.

**Why geometric, not `L=n`:** integer sizes 3,4,5,… waste runs on tiny steps and then
jump by huge relative amounts. A geometric ladder gives uniform resolution in
\(\log n\), which is what the frontier estimate needs.

---

## 2. The score: 50% frontier, no ceiling

For a model \(m\), at each tested level \(L\):

- \(k_L\) valid tasks attempted,
- \(c_L\) correct,
- \(p_L = c_L/k_L\).

Apply **isotonic regression** (non-increasing in \(L\)) to suppress noise and
non-monotonic lucky solves. Find adjacent levels \(k,k+1\) with

\[
\hat p_k \ge 0.5 > \hat p_{k+1}.
\]

Interpolate in \(\log n\):

\[
\log n^* = \log n_k +
\frac{\hat p_k - 0.5}{\hat p_k - \hat p_{k+1}}
\left(\log n_{k+1} - \log n_k\right)
\]

Then:

\[
\boxed{\text{EQB-L} = L^* = 1 + 3\log_2(n^*/3)}
\qquad
\boxed{\text{Frontier size} = n^*}
\]

`EQB-L` is the continuous level at which the model has a 50% chance of producing the
exact solution. It is unbounded: a model that moves from 24×24 to 48×48 moves from
roughly `L10` to `L13`.

### Why this stays consistent when the ladder grows

1. **Extension invariance.** If the 50% point is bracketed at L7/L8, adding L9–L30
   does not change the score. This is the property the current normalized score lacks.
2. **No dilution.** The score is not divided by the number of levels or tasks. Adding
   tasks or levels does not mechanically lower everyone's score.
3. **Monotone.** If model A's smoothed success curve is at least model B's at every
   level, A's frontier is at least B's.
4. **Censoring is explicit.** If a model passes every tested level, report
   `EQB-L ≥ Lmax`, not a fake finite number. Extend until it fails.
5. **Ladder-independent unit.** `n*` is the physical quantity; `L*` is a convenient
   log-scale label. If the ladder resolution changes, `n*` remains comparable.
6. **Incremental runs.** Old rows do not need to be rerun when a new level is added.
   A model's score only changes if it attempts the new level. This is a major cost and
   credibility advantage.

### Confidence intervals

Bootstrap the tasks within each level, rerun isotonic regression, recompute \(\log n^*\).
Report the 2.5–97.5 percentiles for `EQB-L` and `n*`. Use paired bootstrap across models
so all models are evaluated on the same resampled tasks.

With only 5 tasks per level, the interval is wide. The protocol below adds 5 extra tasks
at the two bracket levels, giving 10 tasks where the estimate actually matters. This is
much cheaper than running 10 tasks at every level.

### Censoring and edge cases

| Case | Report |
|---|---|
| `p_1 < 0.5` | `< L1` (or test `L0`, n=2, if desired) |
| Bracket at `k/k+1` | finite `L*` with CI |
| All tested levels pass | `≥ Lmax`; extend |
| Some levels have <3 valid tasks | mark those levels incomplete; do not use for the bracket |
| Budget cap hit before bracket | `censored_budget`; lower bound only, not ranked |
| Prompt exceeds context | `not_testable`; not a wrong answer |

### Why not just "highest level solved"?

A single lucky solve at a high level would inflate the score. The 50% threshold with
5–10 tasks is robust to one outlier. It also gives a continuous score instead of
integer ties.

---

## 3. Protocol: everyone can run L1 to L∞

### Task bank

- For each level `L` and index `j = 1..10`, derive a task seed from
  `(season_seed, "linear", L, j, generator_version, prompt_version)`.
- The first 5 tasks per level are the **core bank**; tasks 6–10 are the **precision
  bank** used at the bracket.
- All models answer the same tasks at a level. This preserves paired comparisons.
- Public season seed and generator version are published, so anyone can regenerate
  every task. Store only the manifest and seeds in the repo; materialize tasks on
  demand. Run artifacts already contain the prompts and responses.
- Sealed holdout: a separate seed, 5 tasks per level, encrypted. Used to verify top
  rows and future seasons.

### Running a model

```
for L = 1, 2, 3, ...:
    run the 5 core tasks at level L
    compute isotonic p_L
    if the 50% point is bracketed at (L-1, L):
        run the 5 precision tasks at L-1 and L
        stop
    if p_L >= 0.5:
        continue upward
    else:
        stop (frontier is below L)
```

Notes:

- Start at L1 for everyone. Easy levels are cheap; this keeps the protocol simple and
  fair.
- The stopping rule is deterministic given responses. No researcher degrees of freedom.
- A model that is clearly failing can stop early; it does not pay for levels it cannot
  solve.
- A model that passes the public cap (e.g. L17) continues into extension levels until
  it fails or hits the context/cost cap. Extension tasks use the same public seed.
- Optional cost cap: if the cap is reached before the bracket, the row is marked
  `censored_budget` and is not ranked. Budget caps must be declared in the run receipt.

### Reproducibility

- `run.json` records season seed, ladder version, generator version, prompt version,
  dataset/task-bank hash, model ID, provider, API base, price source, reasoning level,
  temperature, max tokens, retry policy, and timestamps.
- `predictions.jsonl` records one row per task with level, `n`, task ID, raw response,
  parsed answer, correctness, status, usage, cost, and latency.
- `eqb verify-ladder` regenerates the bank and checks task IDs, prompts, and answers.
- A new season rotates the seed. Within a season, the ladder and bank are frozen.

### Missing data

- `provider_error`, `timeout`, `missing` → retry; if still failing, mark `infra` and
  exclude from the denominator.
- `wrong`, `unparseable`, `refusal` → 0 (model behavior).
- Require ≥3 valid tasks per level for the level to count. If a model has too many
  infra failures, mark the run `unstable` and exclude it from the official rank.
- Report completion rate and provider-error rate next to every row.

This fixes the current contradiction where provider errors are counted as wrong and
then the whole run is excluded.

---

## 4. Cost efficiency: a second axis, not a hidden composite

The leaderboard should answer three practical questions:

1. **What is the largest system a model can solve?** → `EQB-L`.
2. **What does it cost to find out?** → cost to frontier, total tokens, effective cost.
3. **What is the best model for my budget?** → Pareto and budget tables.

### Metrics

- **Cost to frontier:** actual provider-reported spend for the staircase run.
- **Effective cost:** total spend including retries and infra failures divided by valid
  completed tasks. This penalizes unstable providers.
- **Cost per 100 valid tasks:** comparable to the current metric.
- **Tokens:** input, output, reasoning, and total.
- **Cost basis:** `api_list`, `subscription_amortized`, `free`, `unknown`. Do not compare
  across bases without a label.
- **Price source and date:** publish input/output prices and where they came from.

### Views

- **Pareto frontier:** `EQB-L` vs. cost to frontier. Highlight non-dominated models.
- **Best under budget:** for $1, $5, $20, $100, show the highest frontier.
- **Cheapest within Δ:** for target frontiers L8/L10/L12, show the cheapest model that
  reaches them.
- **Frontier curve:** success probability vs. `L`, with the `L*` marker. This is the hero
  chart; it shows capability shape, not just a rank.
- **Stability panel:** valid completion rate, provider-error rate, repeat agreement at
  the bracket level.

Do **not** collapse capability and cost into a single arbitrary ratio as the primary
rank. A two-axis scorecard plus a Pareto view is easier to defend and more useful.
If a single number is desired, publish an optional `EQB-L per $100` with a caveat.

---

## 5. Model slate: cheaper, stable, reproducible

### Selection criteria

1. Publicly available, **versioned** model ID via a direct API.
2. Stable published pricing; no subscription-only routing for official rows.
3. Context ≥32k tokens (enough for the core ladder).
4. Low provider-error rate in a pilot.
5. Either non-dominated on frontier/cost or a useful price point.
6. Identity verifiable: the API's reported model ID matches the requested ID.

A leaderboard with 5 stable rows is stronger than 20 rows with provider errors.
If a model is only available through a private gateway, mark it `private` and put it in
a separate division; do not mix it into the public official rank.

### Pilot before committing

Run 5 tasks at L6, L8, and L10, two repeats each (30 calls per model). Measure:

- valid completion rate after retries,
- parse rate,
- provider-error rate,
- cost and tokens,
- per-level variance,
- repeat agreement at the same level.

Keep models with:

- ≥95% valid completion,
- ≥95% parse rate,
- ≥90% repeat agreement,
- no silent model-version changes,
- a non-dominated cost/frontier position.

Drop redundant models that are dominated on both axes. Re-run the pilot each season.

### Candidate slate

Use direct APIs where possible. `opencode-go`/aggregator routing is fine for
exploration, but the current full runs show 31–70 provider errors per 70 tasks; that is
not acceptable for official rows.

| Tier | Candidate | Why | Watch |
|---|---|---|---|
| Anchor cheap | DeepSeek V4.1 Flash (direct) | Best current cheap result; already direct | — |
| Cheap | GPT-5.6 Luna (direct OpenAI) | Low cost, stable provider | verify versioned ID |
| Cheap | Claude Haiku 5.5 (direct Anthropic) | Low cost | aggregator had 36/70 errors; use direct |
| Cheap | GLM-5.3 Flash (direct Z.ai) | Low cost | measure timeouts |
| Cheap | MiMo v2.6 Flash (direct Xiaomi) | Very low cost | 19 timeouts in preview |
| Cheap | MiniMax M3 (direct) | Low cost | 70/70 errors via aggregator; use direct |
| Free/open | LongCat 2.5 Preview | Free reference | 20 timeouts; open division |
| Frontier reference | GPT-6.1 Sol (direct) | Calibrates the top | expensive; one row |

Validate availability and pricing before locking the list. Add 1–2 open-weight models
served by a stable, pinned provider if available; they are inexpensive and
reproducible. Prefer models that a reader can actually call.

### Reasoning effort

Use one setting for the official division, and record the actual reported level. `max`
is expensive; if the budget is tight, run a `standard` division at `high`/`medium` and a
separate `max` division for the frontier reference. Do not mix efforts in one ranking.
The staircase already cuts most of the cost; the remaining driver is reasoning tokens
on hard levels.

---

## 6. Repository simplification

The multi-track version is ~5,500 lines across 24 modules, 7 generators, 7 datasets, and
a 7-track site. Linear-only can be roughly half that, with a much clearer story.

### Archive first

1. `git init`
2. commit everything as `v1-multitrack`
3. tag it
4. move `.secrets/` outside the repo
5. only then delete/archive

Do not delete anything before the tag exists.

### Target tree

```
.
├── README.md                  # short landing page
├── CHANGELOG.md
├── CITATION.cff
├── LICENSE
├── Makefile
├── pyproject.toml
├── uv.lock
├── config/
│   ├── models.toml            # evaluated models only
│   └── pricing.toml           # price source + date
├── datasets/
│   └── linear-v2/             # manifest + seeds; tasks materialized on demand
├── docs/
│   ├── methodology.md
│   ├── ladder.md
│   ├── leaderboard.md
│   ├── results.md             # v1 archive
│   ├── seasons/2026-10.md
│   └── design-notes.md
├── runs/
│   └── official/              # clean ranked runs only
├── site/                      # generated; CI deploys to Pages
├── scripts/
│   ├── build_site.sh
│   └── verify_all.sh
├── src/equationbench/
│   ├── __init__.py
│   ├── cli.py
│   ├── ladder.py              # n(L), task generation, bank
│   ├── dataset.py
│   ├── mathutil.py            # Bareiss, formatting
│   ├── prompts.py             # one linear prompt
│   ├── providers/
│   ├── runner.py
│   ├── scoring.py             # frontier score
│   ├── leaderboard.py
│   ├── verify.py
│   ├── types.py
│   └── web/
└── tests/
```

### Remove

- `generation/arith.py`, `poly.py`, `calculus.py`, `modular.py`, `matrix.py`,
  `recurrence.py`; keep only linear.
- Other datasets, leaderboard directories, and stale run directories.
- The 18 one-off shell scripts; replace with Makefile targets and two scripts.
- `server.py` and `db.py` if the static site + GitHub PR submission flow is enough.
  This also removes FastAPI/uvicorn/pydantic from the dependency surface.
- `sympy` from runtime dependencies; keep it in `dev` for independent cross-checks.
- `FAMILIES`, `LEVEL_LABELS`, `HARD_LEVELS`, `linear_overrides`,
  `difficulty_overrides`, track filters, and the 7-bar UI.
- All hand-maintained results tables; generate them from `leaderboard.json`.

### Add

- `ladder.py` with `n_for_level(L)`, `level_for_n(n)`, `build_task(L, j, seed)`.
- `eqb ladder` to print L, n, prompt tokens, and estimated cost.
- `eqb run-frontier` with `--tasks-per-level 5`, `--precision-tasks 5`,
  `--max-level`, `--cost-cap`, `--extend`.
- `scoring.py` frontier functions: isotonic regression, `log n*`, bootstrap CI,
  censoring, rank intervals.
- `eqb verify-ladder` and `eqb verify-run` (hash, coverage, infra rate, re-score).
- CI: `ruff`, `pytest`, dataset verify, site build, link check.
- GitHub Pages deploy.
- One `site/` with the frontier curve, Pareto chart, budget table, and model pages.
- README rewrite, OG image, favicon, screenshot, "run it" and "submit" sections.

### Versioning

- `v2.0.0`, `DATASET_VERSION="v2"`, `SCORING_VERSION="2.0"`,
  `LADDER_VERSION="1"`, `GENERATOR_VERSION="2.0.0"`, `PROMPT_VERSION="2.0"`.
- v1 rows are archived and explicitly not comparable.
- `EQB-L` has no upper bound. The old `0–100` score is retired.

---

## 7. Roadmap

| Phase | Effort | Deliverable | Exit criterion |
|---|---:|---|---|
| 0. Freeze | 0.5 day | `git init`, tag `v1-multitrack`, move secrets, backup | Nothing can be lost |
| 1. Linear-only skeleton | 1–2 days | remove other tracks, `ladder.py`, prompt, dataset manifest, CLI | `eqb run-frontier` produces a run |
| 2. Frontier scoring | 1–2 days | isotonic + interpolation + bootstrap CI + censoring + tests | Synthetic curves recover known `L*` |
| 3. Pilot models | 1–2 days | 30-call pilot per candidate, stability table | 5–7 stable models selected |
| 4. Official runs | 2–4 days | staircase runs, extension for top models, sealed check | Clean rows with brackets, not censored |
| 5. Site + cleanup | 2–3 days | one site, frontier chart, Pareto/budget, README, CI/Pages | Live URL; no stale artifacts |
| 6. Launch | 2–3 days | blog post, case study, HN/Reddit/X, submission flow | First external row |

Total: roughly 1.5–2 focused weeks, depending on model spend.

---

## 8. First actions

1. `git init`; commit as `v1-multitrack`; tag it; move `.secrets/` out.
2. Write `ladder.py` and a `eqb ladder --max-level 20` table (L, n, prompt tokens).
3. Generate 10 tasks at L10 and L12; time generation and verify exact answers.
4. Implement frontier scoring with synthetic tests (known curve → known `L*`).
5. Run the 30-call pilot on 6–8 candidates; drop unstable/dominated models.
6. Run the staircase for 3 models; confirm the bracket is found and the score is
   extension-invariant.
7. Delete/archive the six other tracks, old datasets, old leaderboards, and old runs.
8. Build one site with the frontier curve and Pareto chart; deploy to Pages.
9. Rewrite the README; move v1 history to `docs/results.md`.
10. Launch with 5 clean rows and a clear "submit your model" path.

---

## 9. Open decisions

1. **Coefficient bound.** Start with fixed `B=30`, `X=9`. If the frontier lands too high
   or too low, adjust once in a pilot and freeze it for the season. Do not scale `B`
   with `L`; keep `n` as the only axis.
2. **Official cap.** `L17` (121×121, ~31k prompt tokens) is a safe common cap. `L20`
   (242×242) is available for long-context models. Pick one for the official division
   and label extensions separately.
3. **Staircase vs. fixed core.** Recommended: staircase from L1, 5 core + 5 precision
   tasks at the bracket. A fixed L1–L12 core is simpler for readers but wastes money on
   weak models.
4. **Single effort or two divisions.** Recommended: one official effort for
   comparability; add a cheaper division only if the budget forces it.
5. **Server vs. static submissions.** Recommended: static site + GitHub PR template +
   `eqb verify-run`; remove the FastAPI submission server for minimalism.
6. **Public vs. private model rows.** Official rows must be publicly reproducible. Put
   private-gateway models in a separate division or mark them clearly.

---

## 10. Why this is the right portfolio story

> Most benchmarks are fixed sets that saturate. EquationBench Linear removes the fixed
> set. It generates dense linear systems on a geometric ladder from 3×3 to 242×242,
> measures the 50% frontier, and reports it alongside the cost to get there. Because
> the ladder extends, the score has no ceiling. Because every task is exact, there is
> no judge. Because cheap models stop early, the benchmark is affordable to run.

That is a clear, memorable, technically defensible project. It also produces better
visuals: a frontier curve, a Pareto chart, and a "cheapest model that can solve 24×24"
table — all more useful than a 0–100 leaderboard.
