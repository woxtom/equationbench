# Submitting a Run

EquationBench accepts two kinds of rows:

1. **Official runs** produced by the maintainers with the public harness.
2. **Community runs** submitted with complete artifacts and reviewed before being
   marked as community results.

A row is not official until it has a clean run receipt, full coverage of the
declared task bank, and a provider/route disclosure.

## 1. Install and verify

```bash
git clone <this-repo> equationbench
cd equationbench
uv sync --extra dev
uv run pytest
uv run eqb ladder --max-level 20
```

## 2. Add a model

Add a `[[models]]` block to `config/models.toml`:

```toml
[[models]]
key = "my-lab-my-model"
name = "My Model"
lab = "My Lab"
provider = "openai"
model = "my-model-versioned-id"
thinking = "max"
division = "standard"
color = "#5eead4"
notes = "Direct API; versioned model id; pricing source and date."
```

Prefer a direct, versioned API. Aggregator routes are allowed for exploration,
but an official row must disclose the route and have a measured provider-error
rate.

## 3. Run the protocol

Use `eqb run-ladder --model my-lab-my-model --levels 1-11`. The adaptive
runner is not wired yet. Scoring v3 integrates success over a shared grid:

- Run 5 core tasks at every whole level L1–L11.
- Use a predeclared precision allocation of up to 5 extra tasks per level.
- Do not stop merely because the success rate crosses 50%.
- Half levels are optional diagnostics, not scoring knots.
- Missing scoring levels can produce bounds and an unranked row. Inferred
  monotone plateaus are disclosed; full measured coverage is preferable.
- A horizon extension must apply to all compared rows, not just one model.
- Record raw responses, usage, cost, latency, provider, route, and reasoning level.

## 4. Validate the artifacts

A run directory must contain:

```
run.json            # model, provider, route, task bank hash, config, timestamps
predictions.jsonl   # one row per task: level, n, task_id, response, status, usage
summary.json        # eqb area score, interval/bounds, cost, completion rate
eqb.json            # v3 score, horizon, inferred/unresolved/ignored levels
```

Check:

- `run.json` task ids match the published ladder bank;
- the task-bank hash matches;
- every level has at least 3 valid tasks;
- provider errors and timeouts are marked `infra`, not `wrong`;
- all whole-level scoring knots are identified, or the row explicitly shows bounds;
- scoring version and horizon match the comparison;
- at least 90% of all tasks are valid for a provisional ranked row (100% for official);
- cost basis and pricing source are recorded.

## 5. Open a pull request

Add:

- the `[[models]]` entry;
- the run directory under `runs/community/<run-id>/`;
- a short disclosure note: provider, route, model version, reasoning setting,
  temperature, max tokens, pricing source, and anything unusual.

Do not edit predictions. Do not hide failed or provider-error tasks. A run with
a mismatched hash, missing coverage, or unexplained infrastructure failures will
be rejected or shown as unranked.

## 6. Verification

A sealed holdout for verifying top community rows is planned but not implemented
yet.

## Code of conduct

Be precise about what the row measures. Do not claim state-of-the-art from a
single noisy run, a censored row, or a non-comparable reasoning setting.
