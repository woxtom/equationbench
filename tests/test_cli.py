from __future__ import annotations

import json

from typer.testing import CliRunner

from equationbench.cli import app


def test_version_and_list_models():
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "EquationBench" in result.output
    result = runner.invoke(app, ["list-models", "--enabled-only"])
    assert result.exit_code == 0
    assert "GPT-6 Sol" in result.output


def test_ladder_table_and_json():
    runner = CliRunner()
    result = runner.invoke(app, ["ladder", "--max-level", "10"])
    assert result.exit_code == 0, result.output
    assert "linear ladder" in result.output
    assert "24" in result.output

    result = runner.invoke(app, ["ladder", "--max-level", "3", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["official_cap_level"] == 17
    assert len(payload["levels"]) == 3
    assert payload["levels"][0]["size"] == 3
    assert payload["levels"][2]["size"] == 5


def test_ladder_measure_generates_real_prompts():
    runner = CliRunner()
    result = runner.invoke(app, ["ladder", "--max-level", "2", "--measure"])
    assert result.exit_code == 0, result.output
    assert "linear ladder" in result.output


def test_build_and_verify_dataset(tmp_path):
    runner = CliRunner()
    out = tmp_path / "dataset"
    result = runner.invoke(
        app,
        ["build-dataset", "--profile", "dev", "--out", str(out), "--per-cell", "1"],
    )
    assert result.exit_code == 0, result.output
    assert (out / "tasks.jsonl").exists()
    result = runner.invoke(app, ["verify-dataset", "--path", str(out)])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_enabled_models_default_to_max_reasoning():
    from equationbench.providers import load_models

    models = load_models("config/models.toml")
    assert models
    assert all(model.thinking == "max" for model in models if model.enabled)
