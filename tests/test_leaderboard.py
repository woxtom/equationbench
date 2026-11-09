"""Tests for the generated leaderboard builder."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from equationbench import leaderboard as builder
from equationbench.cli import app

ROOT = Path(__file__).resolve().parents[1]


def test_official_run_is_recomputed_and_rankable() -> None:
    row = builder.load_run(
        ROOT / "runs" / "official" / "2026-10" / "deepseek-v4-1-flash",
        bootstrap=0,
        root=ROOT,
    )
    assert row is not None
    assert row["official"] is True
    assert row["rankable"] is True
    assert row["score"] == pytest.approx(9.581826687639762)
    assert row["scoring_version"] == "3.0"
    assert row["horizon"] == 11
    assert "composite" not in row and "band_rate" not in row
    assert row["valid"] == 75
    assert row["precision_levels"] == [9, 10, 11]
    assert row["provider_errors"] == 0
    assert row["dataset_hash_ok"] is True


def test_incomplete_probe_is_not_rankable() -> None:
    row = builder.load_run(
        ROOT / "runs" / "_archive" / "probes" / "2026-10" / "batch" / "anthropic-claude-haiku-5-5",
        bootstrap=0,
        root=ROOT,
    )
    assert row is not None
    assert row["rankable"] is False
    assert row["reasons"]


def test_score_labels_cover_bounds() -> None:
    assert builder.score_label({"score": 9.25}) == "9.25"
    assert (
        builder.score_label({"score": None, "score_bounds": [3.49, 3.84]}) == "3.49–3.84 [bounds]"
    )
    assert builder.score_label({"score": None}) == "—"


def test_web_page_and_pages_workflow_exist() -> None:
    page = ROOT / "docs" / "index.html"
    workflow = ROOT / ".github" / "workflows" / "pages.yml"
    assert page.is_file()
    assert workflow.is_file()
    html = page.read_text(encoding="utf-8")
    assert "data/leaderboard.json" in html
    assert "data/leaderboard.csv" in html
    assert "Score against cost" in html
    assert "Score against tokens" in html
    assert 'id="chart-cost"' in html
    assert 'id="chart-tokens"' in html
    assert "function scatter" in html
    yml = workflow.read_text(encoding="utf-8")
    assert "upload-pages-artifact" in yml
    assert "deploy-pages" in yml


def test_leaderboard_json_has_fields_the_page_uses() -> None:
    import json

    payload = json.loads((ROOT / "data" / "leaderboard.json").read_text(encoding="utf-8"))
    assert payload["rows"]
    for row in payload["rows"]:
        for key in (
            "rank",
            "model",
            "effort",
            "rankable",
            "official",
            "correct",
            "n_tasks",
            "coverage",
            "cost_known",
            "score_bounds",
            "horizon",
            "scoring_version",
        ):
            assert key in row, key


def _tiny_repo(tmp_path: Path) -> Path:
    receipt = "runs/official/2026-10/deepseek-v4-1-flash"
    shutil.copytree(ROOT / receipt, tmp_path / receipt)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "leaderboard-notes.md").write_text("## Notes\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "before\n<!-- leaderboard:start -->\nold\n<!-- leaderboard:end -->\nafter\n",
        encoding="utf-8",
    )
    return tmp_path


def test_build_writes_files_and_check_detects_drift(tmp_path) -> None:
    root = _tiny_repo(tmp_path)
    runner = CliRunner()
    args = ["build-leaderboard", "--root", str(root), "--bootstrap", "0"]

    assert runner.invoke(app, [*args, "--check"]).exit_code == 1

    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert (root / "data" / "leaderboard.json").is_file()
    assert (root / "data" / "leaderboard.csv").is_file()
    assert "## Notes" in (root / "docs" / "leaderboard.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "DeepSeek V4.1 Flash" in readme and "old" not in readme
    assert readme.startswith("before\n") and readme.endswith("after\n")

    assert runner.invoke(app, [*args, "--check"]).exit_code == 0

    (root / "data" / "leaderboard.csv").write_text("tampered", encoding="utf-8")
    assert runner.invoke(app, [*args, "--check"]).exit_code == 1


def test_readme_without_markers_is_an_error() -> None:
    with pytest.raises(ValueError, match="markers"):
        builder.render_readme("no markers here", [])


def test_deepseek_max_ranks_above_high_from_receipts():
    rows = [
        builder.load_run(ROOT / path, bootstrap=0, root=ROOT)
        for path in (
            "runs/official/2026-10/deepseek-v4-1-flash",
            "runs/provisional/2026-10/high/deepseek-v4-1-flash",
        )
    ]
    ranked, unranked = builder.rank_rows(rows)
    assert not unranked
    assert [row["effort"] for row in ranked] == ["max", "high"]
    assert ranked[0]["score"] > ranked[1]["score"]


def test_missing_easy_levels_are_unranked_not_assumed_perfect():
    row = builder.load_run(
        ROOT / "runs/provisional/2026-10/high/openai-gpt-6-luna", bootstrap=0, root=ROOT
    )
    assert row["rankable"] is False
    assert row["score"] is None
    assert row["unresolved_levels"] == [1, 2]
    assert row["score_bounds"][0] < row["score_bounds"][1]
    assert "[bounds]" in builder.score_label(row)


def test_exact_score_ties_do_not_use_cost_or_raw_solve_counts():
    rows = [
        {"run_dir": "a", "rankable": True, "score": 8, "correct": 100, "cost_usd": 1},
        {"run_dir": "b", "rankable": True, "score": 8, "correct": 10, "cost_usd": 10},
        {"run_dir": "c", "rankable": True, "score": 7},
    ]
    ranked, _ = builder.rank_rows(rows)
    assert [row["rank"] for row in ranked] == [1, 1, 3]


def test_active_outputs_retire_composite_and_band():
    import json

    payload = json.loads((ROOT / "data/leaderboard.json").read_text())
    assert payload["scoring_version"] == "3.0"
    for row in payload["rows"]:
        assert "composite" not in row
        assert "band_rate" not in row
        assert "size" not in row
    page = (ROOT / "docs/index.html").read_text()
    assert ".composite" not in page and "bandCell" not in page
    assert "EQB-L" not in page and "EQB-C" not in page
