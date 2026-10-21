# Submitting a Model

EquationBench accepts two kinds of results:

1. **Official runs** — produced by the maintainers with this harness on the fixed public test set, with full task coverage. These are ranked by default.
2. **Self-reported runs** — produced by another lab or individual and submitted with complete artifacts. They are reviewed and marked as self-reported until reproduced. A top self-reported entry can be re-run against the sealed holdout before being marked verified.

The initial public leaderboard contains official runs only. The submission workflow below is the path for adding a model without waiting for the maintainers.

## 1. Install the harness

```bash
git clone <this-repo> equationbench
cd equationbench
uv venv --python 3.12
uv pip install -e ".[dev]"
eqb verify-dataset --path datasets/equationbench-v1-test
```

You should see `OK 70 tasks` and the dataset hash printed by the command. If the hash does not match the leaderboard's dataset commitment, stop: you are on a different benchmark version.

## 2. Add a model entry

Edit `config/models.toml` and add a `[[models]]` block:

```toml
[[models]]
key = "my-lab-my-model"
name = "My Model"
lab = "My Lab"
provider = "opencode-go"        # any pi provider
model = "my-model-id"
thinking = "off"
division = "standard"
color = "#5eead4"
notes = "Short provider/routing disclosure."
```

For a self-hosted or external OpenAI-compatible server:

```toml
[[models]]
key = "my-lab-local"
name = "My Model (local)"
lab = "My Lab"
provider = "local"
provider_kind = "openai-compatible"
base_url = "https://my-endpoint.example/v1"
api_key_env = "MY_API_KEY"
model = "my-model-id"
thinking = "off"
division = "self-hosted"
color = "#5eead4"
```

`provider_kind = "pi"` uses the `pi` CLI and its authenticated provider catalog. `provider_kind = "openai-compatible"` calls `/chat/completions` directly and is intended for vLLM, Ollama, LM Studio, OpenRouter, and similar servers.

## 3. Run the fixed test set

```bash
export MY_API_KEY=...          # if using a direct endpoint
eqb run \
  --model my-lab-my-model \
  --dataset datasets/equationbench-v1-test \
  --concurrency 4 \
  --timeout 0 \
  --thinking max \
  --retries 2 \
  --out runs/my-lab-my-model
```

Do not modify the prompt, the task set, the answer contract, or the parser. Do not give the model tools, retrieval, a Python interpreter, or a scratchpad with execution. A legitimate run is closed-book and single-turn.

The run directory will contain:

```
runs/my-lab-my-model/
  run.json            # model, dataset hash, selected ids, config, environment
  predictions.jsonl   # one row per task: raw response, parsed answer, usage, cost
  summary.json        # score, CIs, per-track/level breakdown, run metadata
```

## 4. Validate the run

```bash
eqb score --run runs/my-lab-my-model
```

Check the printed summary and then verify the run metadata manually:

- `run.json.dataset.dataset_sha256` equals the published test hash;
- `run.json.dataset.selected_tasks` has exactly 70 ids;
- `run.json.status` is `complete`;
- `summary.json.score.completion_rate` is `1.0`;
- `summary.json.score.n` is 70.

A partial run, a mismatched dataset hash, a missing prediction, or an aborted run will be excluded from the official ranking.

## 5. Rebuild the leaderboard locally

```bash
eqb leaderboard build \
  --runs runs \
  --dataset datasets/equationbench-v1-test

python -m http.server 8000 --directory leaderboard
```

Your model should appear in the table with its score, interval, per-track profile, cost, and latency. Open the model page and inspect the sample answers. If the parser rejected a correct answer, open an issue with the task id and raw response; do not silently edit predictions.

## 6. Submit the artifacts

Preferred: open a pull request that adds:

- the new `[[models]]` entry;
- the run directory under `runs/<run-id>/` (including `run.json`, `predictions.jsonl`, and `summary.json`);
- a short note in the PR describing provider, routing, thinking level, and any unusual configuration.

If you cannot open a PR, use the submission endpoint:

```bash
# Server-side review queue (requires the admin token when configured)
eqb serve --db eqb.sqlite --port 8000

curl -X POST http://localhost:8000/api/submissions \
  -H "Content-Type: application/json" \
  -H "X-EQB-Token: $EQB_ADMIN_TOKEN" \
  -d @submission.json
```

The server validates the dataset hash, task ids, prediction coverage, and recomputes the score from predictions. It never trusts a submitted score.

A submission is **self-reported** until a maintainer reproduces it. Reproduction may use a fresh provider account, the sealed holdout, or both. The leaderboard shows the verification status.

## 7. Rules and disclosure

A valid entry must:

- use the exact public test set and the exact prompt wrapper;
- run with tools, code execution, retrieval, and external resources disabled;
- produce one final answer per task;
- report the actual model id, provider, and reasoning level;
- include all predictions, including failures, timeouts, refusals, and unparseable answers;
- disclose any provider routing, quantization, system-prompt customization, or sampling settings that differ from the default;
- not train on the public test answers during the run;
- not use the sealed holdout without maintainer coordination.

Do not:

- remove failed tasks or rerun only the failures and merge the results;
- edit `predictions.jsonl` to replace an answer;
- use a model-specific prompt that leaks task-specific hints;
- submit a score without artifacts;
- claim a sealed result without a signed run receipt.

Repeated attempts at the same task are allowed in a research log, but the leaderboard row must correspond to a single deterministic configuration (one attempt per task unless retries are only for transport errors). The harness retries only transient provider failures, not wrong answers.

## 8. Verification tiers

| Tier | Meaning | Shown as |
|---|---|---|
| Official | Maintainer-run, full public set, artifacts committed | `verified` |
| Self-reported | Submitted with complete artifacts; not yet reproduced | `self-reported` |
| Sealed-verified | Top entry reproduced on the encrypted holdout | `sealed` |
| Preview | Partial set or non-standard configuration | `preview` |

The initial release ranks official runs. Self-reported and sealed tiers are part of the submission roadmap; the data format already carries the fields needed for them.

## 9. Improving the benchmark

Contributions are welcome for:

- new task families with exact ground truth and a clear difficulty ladder;
- generators that remain deterministic and bounded in runtime;
- parser cases that are semantically unambiguous;
- statistical improvements that preserve transparency;
- documentation, examples, and reproducibility checks.

Open an issue before adding a new track. A new track changes the dataset hash and therefore requires a version bump.
