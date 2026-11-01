"""Tests for the generated leaderboard builder."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_leaderboard.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_leaderboard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_official_run_is_recomputed_and_rankable() -> None:
    builder = load_builder()
    row = builder.load_run(
        ROOT / "runs" / "official" / "2026-10" / "deepseek-v4-1-flash",
        bootstrap=0,
    )
    assert row is not None
    assert row["official"] is True
    assert row["rankable"] is True
    assert row["score"] == 10.0
    assert row["valid"] == 70
    assert row["precision_levels"] == [9, 10, 11]
    assert row["provider_errors"] == 0
    assert row["dataset_hash_ok"] is not False


def test_incomplete_probe_is_not_rankable() -> None:
    builder = load_builder()
    row = builder.load_run(
        ROOT / "runs" / "_archive" / "probes" / "2026-10" / "batch" / "anthropic-claude-haiku-5-5",
        bootstrap=0,
    )
    assert row is not None
    assert row["rankable"] is False
    assert row["reasons"]


def test_score_labels_cover_censoring() -> None:
    builder = load_builder()
    assert builder.score_label({"score": 9.25}) == "9.25"
    assert builder.score_label({"score": None, "censored": "upper", "bound": 11.0}) == "≥11.0"
    assert builder.score_label({"score": None, "censored": "lower", "bound": 3.0}) == "<3.0"
    assert builder.score_label({"score": None, "censored": "ambiguous", "bound": 7.0}) == "~7.0"
