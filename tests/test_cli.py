from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from equationbench.cli import app
from equationbench.types import Completion

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_list_models():
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "EquationBench" in result.output
    result = runner.invoke(app, ["list-models", "--enabled-only"])
    assert result.exit_code == 0
    assert "DeepSeek V4.1 Flash" in result.output


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


def test_model_registry_uses_declared_thinking_levels():
    from equationbench.providers import load_models

    allowed = {"off", "minimal", "low", "medium", "high", "xhigh", "max"}
    models = load_models("config/models.toml")
    assert models
    enabled = [model for model in models if model.enabled]
    assert enabled
    assert all(model.thinking in allowed for model in enabled)
    assert any(model.thinking == "max" for model in enabled)


def test_score_rescores_a_ladder_receipt(tmp_path):
    run = tmp_path / "run"
    shutil.copytree(ROOT / "runs" / "official" / "2026-10" / "deepseek-v4-1-flash", run)
    result = CliRunner().invoke(app, ["score", "--run", str(run), "--bootstrap", "0"])
    assert result.exit_code == 0, result.output
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    assert summary["eqb"]["score"] == pytest.approx(9.581826687639762)
    assert summary["eqb"]["scoring_version"] == "3.0"
    assert "frontier" not in summary
    assert json.loads((run / "eqb.json").read_text())["eqb"] == summary["eqb"]
    assert summary["score"]["n"] == 75


def _frontier_args(*extra):
    return ["run-ladder", "--model", "deepseek-v4-1-flash", "--levels", "2-3", *extra]


def test_run_frontier_dry_run_makes_no_calls(monkeypatch):
    def fail(spec):
        raise AssertionError("dry run must not build a provider")

    monkeypatch.setattr("equationbench.runner.make_provider", fail)
    result = CliRunner().invoke(app, _frontier_args("--dry-run"))
    assert result.exit_code == 0, result.output
    assert "Dry run" in result.output


def test_run_frontier_rejects_bad_options():
    runner = CliRunner()
    assert runner.invoke(app, ["run-frontier", "--all", "--levels", "5-2"]).exit_code == 2
    assert runner.invoke(app, ["run-frontier", "--all", "--levels", "99"]).exit_code == 2
    assert (
        runner.invoke(
            app, _frontier_args("--precision-levels", "9", "--precision-tasks", "1")
        ).exit_code
        == 2
    )


def test_run_frontier_end_to_end_with_a_fake_provider(monkeypatch, tmp_path):
    from equationbench.ladder_run import build_ladder_bundle

    answers = {task.prompt: task.answer for task in build_ladder_bundle([2, 3]).tasks}

    class Solver:
        def __init__(self, spec):
            self.spec = spec

        def complete(self, system, prompt, timeout):
            n = len(json.loads(answers[prompt]))
            # Solve the 4-variable level, fail the 5-variable level.
            text = answers[prompt] if n == 4 else "[" + ", ".join(["0"] * n) + "]"
            return Completion(text=f'{{"answer": {text}}}', cost_usd=0.01, latency_ms=5)

    monkeypatch.setattr("equationbench.runner.make_provider", Solver)
    out = tmp_path / "run"
    result = CliRunner().invoke(app, _frontier_args("--out", str(out), "--bootstrap", "0"))
    assert result.exit_code == 0, result.output
    payload = json.loads((out / "eqb.json").read_text(encoding="utf-8"))
    assert payload["status"] == "complete"
    assert payload["completion"] == 1.0
    from equationbench.ladder import level_for_size

    assert payload["eqb"]["score"] == pytest.approx(level_for_size((4 * 5) ** 0.5))
    assert payload["eqb"]["horizon"] == 11
    assert not (out / "frontier.json").exists()


@pytest.mark.parametrize(
    "args",
    [
        ["--horizon", "1"],
        ["--horizon", "21"],
        ["--levels", "9.5"],
        ["--levels", "12", "--horizon", "11"],
    ],
)
def test_invalid_scoring_plan_fails_before_provider_calls(monkeypatch, args):
    def fail(spec):
        raise AssertionError("invalid plans must not build a provider")

    monkeypatch.setattr("equationbench.runner.make_provider", fail)
    result = CliRunner().invoke(app, _frontier_args(*args))
    assert result.exit_code == 2, result.output


def test_legacy_command_alias_and_custom_horizon():
    result = CliRunner().invoke(
        app,
        [
            "run-frontier",
            "--model",
            "deepseek-v4-1-flash",
            "--levels",
            "12",
            "--horizon",
            "12",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "EQB horizon: L12" in result.output


def test_rescore_rejects_tampered_hash_without_overwriting_summary(tmp_path):
    run = tmp_path / "run"
    shutil.copytree(ROOT / "runs/official/2026-10/deepseek-v4-1-flash", run)
    original = (run / "summary.json").read_bytes()
    receipt = json.loads((run / "run.json").read_text())
    receipt["dataset"]["dataset_sha256"] = "invalid"
    (run / "run.json").write_text(json.dumps(receipt))
    result = CliRunner().invoke(app, ["score", "--run", str(run), "--bootstrap", "0"])
    assert result.exit_code == 2
    assert "hash" in result.output
    assert (run / "summary.json").read_bytes() == original


def test_parse_levels_accepts_half_levels():
    from equationbench.cli import _parse_levels

    assert _parse_levels("9,9.5,10-11") == [9, 9.5, 10, 11]
    assert all(isinstance(level, int) for level in _parse_levels("9.0,10"))


def test_run_frontier_rejects_a_half_level_with_no_size():
    result = CliRunner().invoke(app, ["run-frontier", "--all", "--levels", "2.5"])
    assert result.exit_code == 2
