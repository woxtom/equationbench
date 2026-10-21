# Contributing to EquationBench

EquationBench is a benchmark, so changes to tasks, prompts, or scoring are versioned changes to the measurement instrument. Please open an issue before changing any of those.

## Development

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
uv run pytest
```

The test suite covers all seven generators, answer extraction, exact scoring, uncertainty intervals, dataset integrity, run execution with a fake provider, and static leaderboard generation.

## Adding a model

1. Add a `[[models]]` entry to `config/models.toml`.
2. Run the model on the full public test set:

```bash
eqb run --model <key> --dataset datasets/equationbench-v1-test --concurrency 4
```

3. Inspect the run receipt and sample answers.
4. Rebuild the leaderboard with `eqb leaderboard build`.
5. Submit the run artifacts and a disclosure note as described in [`docs/submission.md`](docs/submission.md).

Do not edit predictions or omit failed tasks. A run is only eligible when it covers the full fixed set and its dataset hash matches.

## Adding a task family

A new family must:

- be a deterministic pure function of `(level, random.Random)`;
- compute ground truth with exact integer/rational arithmetic;
- have a clear five-level difficulty ladder;
- return one of the existing answer types (`integer`, `rational`, `integer_list`);
- be bounded in generation time and answer size;
- include tests for determinism, correctness, and edge cases.

Adding a family changes the dataset hash and therefore requires a version bump. Do not modify the public test set in place.

## Changing prompts or scoring

Prompt changes require `PROMPT_VERSION` to change. Scoring/canonicalization changes require `SCORING_VERSION` to change. Dataset changes require `DATASET_VERSION` to change. Leaderboard rows are only comparable within the same dataset hash and scoring version.

## Data hygiene

- Do not commit `.secrets/`.
- Do not publish decrypted sealed tasks before the reveal date.
- Do not train on public test answers during an official run.
- Do not add private prompts, API keys, or user data to run artifacts.

## Code style

- Python 3.11+.
- Use exact arithmetic; never use floats for ground truth.
- Keep generators bounded and deterministic.
- Prefer small, auditable functions over clever compression.
- Add tests for every non-trivial parser or scoring behavior.

## Reporting issues

Open an issue with:

- the benchmark version and dataset hash;
- the task id;
- the model key and run id;
- the raw response if the issue is about answer parsing;
- a minimal reproduction command.

Corrections to an answer must include a proof or an independent exact computation.
