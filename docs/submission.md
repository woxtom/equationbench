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

The v2 staircase command is not wired yet. Until `eqb run-frontier` lands, a
community run can use the fixed-set v1 harness for continuity, but it is a
different benchmark version.

The intended v2 protocol:

- Start at L1.
- Run 5 core tasks per level.
- Stop when the 50% point is bracketed.
- Run 5 precision tasks at each of the two bracket levels.
- Extend above the public cap until the model fails or hits the context/cost cap.
- Record raw responses, usage, cost, latency, provider, route, and reasoning level.

## 4. Validate the artifacts

A run directory must contain:

```
run.json            # model, provider, route, task bank hash, config, timestamps
predictions.jsonl   # one row per task: level, n, task_id, response, status, usage
summary.json        # frontier score, interval, censoring, cost, completion rate
```

Check:

- `run.json` task ids match the published ladder bank;
- the task-bank hash matches;
- every level has at least 3 valid tasks;
- provider errors and timeouts are marked `infra`, not `wrong`;
- the frontier is bracketed, or the row is explicitly censored;
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

Top community rows may be re-run on the sealed holdout before receiving a
`verified` badge. The sealed seed is published only after the season closes, so
the commitment can be checked.

## Code of conduct

Be precise about what the row measures. Do not claim state-of-the-art from a
single noisy run, a censored row, or a non-comparable reasoning setting.
