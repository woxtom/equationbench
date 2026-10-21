# EquationBench Methodology

**Version 1.0.0 · dataset v1 · scoring v1.0**

This document specifies the task generation, answer contract, scoring, uncertainty estimation, contamination policy, and reproducibility guarantees of EquationBench. It is intended to be sufficient for an independent lab to reproduce a leaderboard row or audit the benchmark.

## 1. What EquationBench measures

EquationBench measures **closed-book exact reasoning over large symbolic or numeric objects**. A model receives one self-contained prompt and must produce one final answer. Tools, code execution, retrieval, and external resources are disabled. The benchmark does not measure tool use, multi-turn collaboration, proof presentation, or approximation quality.

The design target is the regime where:

1. the problem is too large for a single mental arithmetic shortcut,
2. the answer is still exactly checkable,
3. the difficulty can be generated on demand rather than scraped from a fixed corpus.

This makes the benchmark useful for tracking whether models can maintain a multi-step computational plan at scale, and for detecting contamination because new tasks can be generated from a new seed.

## 2. Deterministic generation

Every task is a pure function of:

```
(master_seed, family, level, index, generator_version, prompt_version, attempt)
```

A seed is derived with SHA-256:

```python
seed = int.from_bytes(sha256("|".join(material).encode()).digest()[:8], "big")
rng = random.Random(seed)
```

The task id is:

```python
task_id = sha256(f"{family}:{level}:{seed}:{generator_version}:{prompt_version}").hexdigest()[:16]
```

Consequences:

- The same seed reproduces the same prompt and answer exactly.
- The public sets publish their master seed, so anyone can regenerate them.
- The sealed holdout publishes only a commitment to its seed and plaintext hash.
- A generator change requires a version bump; task ids change automatically.

The task-generation code is in `src/equationbench/generation/`. The dataset builder is in `src/equationbench/dataset.py`. The public development and test sets are generated with master seeds `20261017` and `731992`. The sealed set uses an unpublished 128-bit seed.

## 3. Task families and difficulty

| Family | Object | Answer type | Level 1 → 5 scale |
|---|---|---|---|
| `arith` | Fully parenthesized integer expression | Integer | 6 → 90 operators; leaf magnitude 10 → 100,000; powers and factorials from L3/L4 |
| `poly` | Product of linear factors | Coefficient (integer) | degree 5 → 36; factor coefficients up to 5 → 50 |
| `linear` | Dense integer linear system | Integer vector | 3 → 14 variables; coefficients up to 5 → 30 |
| `calculus` | Factored polynomial | Rational | degree 4 → 22; first/second derivative at a point, or exact integral |
| `modular` | Mixed power-tower expression | Integer | modulus 1,009 → 1,000,000,007; tower height 2 → 5; 1 → 3 towers |
| `matrix` | Integer matrix / matrix polynomial | Integer | 3×3 determinant → 10×10 determinant of \(A^2+cA+dI\) |
| `recurrence` | Constant-coefficient linear recurrence | Integer modulo a prime | order 2 → 5; index \(10^1\) → \(10^{18}\) |

Each family is described in more detail in [tasks.md](tasks.md). The exact parameter tables live in the `LEVEL_SPECS` dictionaries in each generator module; these are the authoritative values.

Difficulty levels are ordinal and are used as weights in the score. They are designed to be monotonically harder in computational state, even when a particular random instance happens to have a short answer. Empirical difficulty is reported on the leaderboard as mean accuracy by level, which is the appropriate calibration check.

## 4. Prompt and answer contract

All models receive the same system prompt and the same task wrapper:

- Tools, code execution, and external resources are unavailable.
- The answer must be exact; no rounding or approximation.
- The response may contain reasoning, but it must end with a single JSON object.
- The JSON object must be the last thing in the response.

The answer shapes are:

| Answer type | Required shape | Example |
|---|---|---|
| Integer | JSON string | `{"answer": "121932631112635269"}` |
| Rational | JSON string, reduced `p/q` or integer | `{"answer": "17/24"}` |
| Integer vector | JSON array | `{"answer": [3, -1, 7]}` |

The parser is deliberately more liberal than the contract:

- last JSON object containing an `answer` key;
- fenced JSON;
- `\boxed{...}`;
- `Answer: ...` / `Final answer: ...`;
- LaTeX `\frac{a}{b}`;
- labeled solutions such as `x1 = 3, x2 = -1`;
- exact arithmetic expressions such as `2^10` or `16/2`.

It is strict about mathematics: a value must canonicalize to exactly the ground truth. Decimal approximations are only accepted when they are exactly equal to the rational value (for example, `0.5` for `1/2`). A floating-point approximation of an irrational or repeating value is rejected.

Canonicalization:

- integers: arbitrary precision, stripped of commas/underscores/spaces;
- rationals: reduced `p/q`, integers when \(q=1\);
- vectors: ordered list of integers.

The evaluation code is in `src/equationbench/verify.py`.

## 5. Time budget

Token throughput varies substantially across providers and models. EquationBench
therefore does not use a per-task wall-clock timeout in the official full-set
protocol. The runner sets `--timeout 0`; a model may take as long as it needs to
emit its final answer. This prevents a fast provider from winning because a slow
provider was cut off mid-computation.

A completed prediction is one of: a parsed answer, a model refusal, an
unparseable response, or a provider error. A provider-level safety limit may be
applied to an individual sweep for operational reasons; if it is used, it must
be reported in the run receipt and treated as part of the protocol. Timeouts, if
they occur, count as incorrect.

The 35-task preview in `datasets`-adjacent run artifacts used a 240-second limit.
It is historical and is labeled as preview; its rows are not comparable to the
no-timeout full-set rows.

## 6. Ground truth

Ground truth is computed at generation time with exact arithmetic only:

- arithmetic expressions use Python big integers;
- polynomial coefficients use integer convolution;
- linear systems are constructed from a known integer solution and checked for a nonzero determinant;
- calculus uses integer polynomial coefficients and `fractions.Fraction`;
- modular towers use prime-power factorization, Euler reduction, and Chinese remaindering;
- matrices use the fraction-free Bareiss determinant;
- recurrences use companion-matrix exponentiation with modular arithmetic.

`eqb verify-dataset` independently regenerates each task from its stored seed and checks both prompt and answer. The test suite cross-checks determinants against SymPy and recurrences against direct iteration on small indices.

No model output is used to define ground truth. No LLM judge is involved.

## 7. Scoring

### EQB Score

The primary metric is difficulty-weighted exact pass@1:

\[
\text{EQB Score} = 100 \cdot \frac{\sum_i \text{level}_i \cdot \mathbb{1}[\text{correct}_i]}{\sum_i \text{level}_i}
\]

where \(i\) ranges over the selected tasks. Raw accuracy is also reported. Missing predictions, provider errors, timeouts, refusals, and unparseable answers count as incorrect for the official score.

Why weight by level? A raw average over a fixed set lets easy tasks hide frontier failures. Weighting preserves the benchmark's intended emphasis on hard tasks while remaining transparent and easy to recompute. The leaderboard also exposes unweighted accuracy and per-level accuracy, so readers can choose their own view.

### Confidence intervals

Intervals are **paired cell-cluster bootstrap** estimates over tasks. We resample `(family, level)` cells with replacement and keep every task in each selected cell. This preserves the benchmark's design and avoids degenerate intervals when a cell has only one task. The same resampled task indices are used for every model in a given replicate. With \(B=2,000\) replicates:

- the 2.5th and 97.5th percentiles give the 95% interval;
- rank distributions give `rank_mean`, `rank_ci`, and `win_probability`;
- the point estimate is computed on the full fixed set, not on the bootstrap mean.

The cell-cluster design matters because the public set is organized as family × level cells. A naive task-level bootstrap can under-represent rare cells; resampling cells keeps the design intact and works for both the 35-task preview (one task per cell) and the 70-task test set (two per cell).

### Pairwise comparisons

For every pair of models, the leaderboard computes a two-sided McNemar test on paired per-task outcomes (exact binomial for small discordant counts, normal approximation above 1,000). The raw p-values are included in `leaderboard/data/leaderboard.json`; they are diagnostic, not a multiple-comparison-corrected significance claim.

### Cost and latency

- Cost is the provider-reported total for the run. The leaderboard shows cost per 100 tasks for comparability.
- If a provider does not report cost, the row shows `n/a` rather than an estimate. Models without cost data are omitted from the cost-performance scatter, not from the ranking.
- Latency is wall-clock provider latency. The leaderboard shows median and p95.
- Token counts include input, output, and reasoning tokens when the provider reports them.

### Reasoning effort

The default division requests the highest reasoning effort (`--thinking max`). Providers differ in what they support:

- some honor `max` literally;
- some clamp `max` to their highest available level (for example `high`);
- a few may ignore the request entirely.

The actual level reported by the transport is recorded in every run and shown on the leaderboard. Earlier full-set runs used `off` and are archived as the standard/off division; they are not directly comparable to the max division.

Every run records the actual `thinkingLevel` reported by the transport. The leaderboard displays it. This is a deliberate transparency choice: EquationBench does not claim that all models used an identical hidden reasoning budget. A future extended division can hold effort at a higher fixed request level.

## 8. Datasets and contamination

### Public development set (`datasets/equationbench-v1-dev`)

35 tasks: one per family × level cell. Includes answers and solution notes. Intended for development, prompt debugging, and harness tests.

### Public test set (`datasets/equationbench-v1-test`)

70 tasks: two per family × level cell. Includes answers and short solution notes. This is the open leaderboard's fixed set. Its master seed is public, so anyone can regenerate it.

### Sealed holdout (`datasets/equationbench-v1-sealed`)

140 tasks: four per family × level cell. Encrypted with Fernet (AES-128-CBC + HMAC-SHA256). The repository publishes:

- the SHA-256 of the plaintext task contents;
- the SHA-256 of the master seed;
- the encrypted payload and its integrity tag.

The key and seed live in `.secrets/` (gitignored) and are not published before the reveal date. Official verification runs use the sealed set. After a season, the key and plaintext are published so the commitment can be checked. Rotating the seed creates a new season and prevents a model from training on revealed tasks.

### Why publish the test set?

A fully hidden benchmark is hard to reproduce and easy to distrust. A fully public benchmark is easy to contaminate. EquationBench uses both: the open set makes every row reproducible, while the sealed set provides a credible check against overfitting. The leaderboard labels runs as verified only when they cover the full fixed set; sealed verification is a separate, maintainer-run process.

### Known limitations

- A model may have seen similar generated expressions during training. Procedural generation reduces, but does not eliminate, this risk.
- Public test answers can be memorized. The sealed holdout is the mitigation.
- Provider routing can change model behavior. The run receipt records provider and model id as reported by the transport.
- Closed-book evaluation penalizes models that would use tools effectively. EquationBench is intentionally a no-tools benchmark; tool use is a separate capability.
- The score is sensitive to prompt format, answer parsing, and reasoning budget. The harness fixes the prompt and publishes the parser; the reasoning level is recorded but not fully controlled.
- Seven tracks do not cover proof writing, geometry, or open-ended modeling. The benchmark is a stress test for exact large-state computation, not a general math ability score.

## 9. Reproducibility protocol

To reproduce a leaderboard row:

```bash
eqb verify-dataset --path datasets/equationbench-v1-test
eqb run --model <model-key> \
  --dataset datasets/equationbench-v1-test \
  --concurrency 4 \
  --out runs/<your-run>
eqb score --run runs/<your-run>
```

Check that:

1. `run.json.dataset.dataset_sha256` matches the published test hash;
2. `run.json.dataset.selected_tasks` is the full set of 70 task ids;
3. `run.json.status` is `complete`;
4. `summary.json.score.n` is 70 and `completion_rate` is 1.0.

A run with a partial set, a mismatched hash, or incomplete coverage is marked preview and is not ranked by default.

The harness is deterministic given the model responses, but the model itself may be nondeterministic. Official results should be reported as a single run with the provider's temperature/sampling defaults. The harness does not set a temperature for pi-routed models; it records the settings it can observe. If a provider supports multiple samples, report the configuration explicitly.

## 10. Versioning

- `GENERATOR_VERSION` changes when task generation changes.
- `PROMPT_VERSION` changes when the prompt contract changes.
- `DATASET_VERSION` changes when the fixed task set changes.
- `SCORING_VERSION` changes when canonicalization or scoring changes.

A leaderboard row is only comparable to rows with the same dataset hash and scoring version. The site displays the dataset version and hash; the JSON contains the generator and prompt versions.

## 11. Citation

```bibtex
@misc{equationbench2026,
  title        = {EquationBench: Procedurally Generated Large-Equation Reasoning},
  author       = {EquationBench Contributors},
  year         = {2026},
  version      = {1.0.0},
  howpublished = {\url{https://github.com/equationbench/equationbench}}
}
```

For questions, corrections, or a sealed verification request, open an issue or use the submission process in [submission.md](submission.md).
