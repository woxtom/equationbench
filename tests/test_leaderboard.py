from __future__ import annotations

import csv

from equationbench.leaderboard import build_leaderboard
from equationbench.providers import load_models
from equationbench.runner import RunConfig, run_benchmark


def test_leaderboard_builds_from_complete_runs(tiny_dataset, fake_provider_factory, tmp_path):
    specs = load_models("config/models.toml")[:3]
    runs_root = tmp_path / "runs"
    for index, spec in enumerate(specs):
        provider = fake_provider_factory(spec, accuracy=[1.0, 0.8, 0.55][index])
        run_benchmark(
            RunConfig(
                model=spec,
                dataset=tiny_dataset,
                out_dir=runs_root / spec.key,
                concurrency=4,
                retries=0,
                provider=provider,
            )
        )
    out = tmp_path / "leaderboard"
    data = build_leaderboard(
        runs_root,
        out,
        dataset_path=tiny_dataset.path,
        bootstrap_replicates=100,
    )
    assert len(data["models"]) == 3
    assert data["benchmark"]["n_tasks"] == 35
    assert (out / "index.html").exists()
    assert (out / "assets" / "style.css").exists()
    assert (out / "data" / "leaderboard.json").exists()
    assert (out / "data" / "leaderboard.csv").exists()
    assert (out / "data" / "task_difficulty.csv").exists()
    assert (out / "docs" / "methodology.html").exists()
    model = data["models"][0]
    assert (out / "models" / f"{model['slug']}.html").exists()
    assert model["score"] >= data["models"][-1]["score"]
    index = (out / "index.html").read_text()
    assert "window.EQB_DATA" in index
    assert model["name"] in index
    with (out / "data" / "leaderboard.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert rows[0]["model"] == model["name"]
    assert data["benchmark"]["families"][0]["n"] == 5
    assert data["benchmark"]["levels"][4]["n"] == 7


def test_preview_scores_common_tasks_only(tiny_dataset, fake_provider_factory, tmp_path):
    specs = load_models("config/models.toml")[:2]
    runs_root = tmp_path / "runs-preview"
    for index, spec in enumerate(specs):
        provider = fake_provider_factory(spec, accuracy=[1.0, 0.7][index])
        run_benchmark(
            RunConfig(
                model=spec,
                dataset=tiny_dataset,
                out_dir=runs_root / spec.key,
                concurrency=4,
                retries=0,
                limit=14,
                provider=provider,
            )
        )
    out = tmp_path / "leaderboard-preview"
    data = build_leaderboard(
        runs_root,
        out,
        dataset_path=tiny_dataset.path,
        bootstrap_replicates=100,
        include_preview=True,
    )
    assert data["benchmark"]["preview"] is True
    assert data["benchmark"]["n_tasks"] == 35
    assert data["benchmark"]["n_tasks_common"] == 14
    assert all(model["n"] == 14 for model in data["models"])
    assert all(model["preview"] for model in data["models"])
    assert data["models"][0]["coverage"] < 0.5


def test_leaderboard_can_score_one_family(tiny_dataset, fake_provider_factory, tmp_path):
    specs = load_models("config/models.toml")[:1]
    spec = specs[0]
    provider = fake_provider_factory(spec, accuracy=1.0)
    runs_root = tmp_path / "runs-linear"
    run_benchmark(
        RunConfig(
            model=spec,
            dataset=tiny_dataset,
            out_dir=runs_root / spec.key,
            concurrency=4,
            retries=0,
            provider=provider,
        )
    )
    data = build_leaderboard(
        runs_root,
        tmp_path / "leaderboard-linear",
        dataset_path=tiny_dataset.path,
        bootstrap_replicates=100,
        families=["linear"],
    )
    assert data["benchmark"]["n_tasks"] == 5
    assert data["benchmark"]["n_tasks_available"] == 35
    assert data["benchmark"]["track_filter"] == ["linear"]
    assert data["benchmark"]["n_tasks_common"] == 5
    assert len(data["benchmark"]["families"]) == 1
    assert data["models"][0]["n"] == 5
    assert data["models"][0]["coverage"] == 1.0
