.PHONY: install test lint ladder measure verify clean

install:
	uv sync --extra dev

test:
	uv run pytest

lint:
	uv run ruff check src tests

ladder:
	uv run eqb ladder --max-level 20

measure:
	uv run eqb ladder --max-level 10 --measure

verify: test ladder

clean:
	rm -rf .pytest_cache .ruff_cache site
	find . -path ./.venv -prune -o -name __pycache__ -type d -exec rm -rf {} +
