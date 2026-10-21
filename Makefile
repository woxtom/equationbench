.PHONY: install test dev test-dataset verify leaderboard serve preview

install:
	uv venv --python 3.12
	uv pip install -e ".[dev]"

test:
	uv run pytest

test-dataset:
	uv run eqb build-dataset --profile dev --out /tmp/equationbench-dev --force

verify:
	uv run eqb verify-dataset --path datasets/equationbench-v1-test

leaderboard:
	uv run eqb leaderboard build --runs runs/full --dataset datasets/equationbench-v1-test

serve:
	uv run eqb serve --port 8000

preview:
	uv run eqb leaderboard build --runs runs/preview --dataset datasets/equationbench-v1-test --include-preview --title "EquationBench Preview Leaderboard"
	python -m http.server 8000 --directory leaderboard

linear-dataset:
	uv run eqb build-dataset --profile linear-test --out datasets/equationbench-v1-test-linear --force

linear-leaderboard:
	uv run eqb leaderboard build --runs runs/full-off --dataset datasets/equationbench-v1-test --family linear --subset-note "retrospective off subset" --out leaderboard-linear
