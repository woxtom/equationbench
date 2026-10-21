from __future__ import annotations

import json

from equationbench.dataset import (
    DatasetProfile,
    dataset_hash,
    load_dataset,
    verify_dataset,
    write_dataset,
)


def test_public_dataset_roundtrip_and_verification(tiny_dataset):
    probs = verify_dataset(tiny_dataset)
    assert probs == []
    loaded = load_dataset(tiny_dataset.path)
    assert len(loaded.tasks) == 35
    assert loaded.manifest["dataset_sha256"] == dataset_hash(loaded.tasks)
    assert loaded.manifest["master_seed"] == 123456789
    assert (tiny_dataset.path / "prompts.jsonl").exists()
    prompt_rows = [
        json.loads(line)
        for line in (tiny_dataset.path / "prompts.jsonl").read_text().splitlines()
    ]
    assert all("answer" not in row for row in prompt_rows)


def test_sealed_dataset_roundtrip(tmp_path):
    profile = DatasetProfile(
        name="sealed-test",
        per_cell=1,
        master_seed=424242,
        sealed=True,
    )
    key_file = tmp_path / "sealed.key"
    seed_file = tmp_path / "sealed.seed"
    bundle = write_dataset(profile, tmp_path / "sealed", key_file=key_file, seed_file=seed_file)
    assert (tmp_path / "sealed" / "sealed.enc").exists()
    assert not (tmp_path / "sealed" / "tasks.jsonl").exists()
    assert bundle.manifest["sealed"] is True
    assert key_file.exists() and seed_file.exists()
    loaded = load_dataset(tmp_path / "sealed", key_file=key_file)
    assert len(loaded.tasks) == len(bundle.tasks)
    assert verify_dataset(loaded) == []
    assert loaded.manifest["dataset_sha256"] == bundle.manifest["dataset_sha256"]


def test_dataset_hash_is_stable(tiny_dataset):
    again = load_dataset(tiny_dataset.path)
    assert dataset_hash(again.tasks) == dataset_hash(tiny_dataset.tasks)


def test_linear_only_dataset_profile(tmp_path):
    profile = DatasetProfile(
        name="linear-test",
        per_cell=1,
        master_seed=731992,
        families=("linear",),
    )
    bundle = write_dataset(profile, tmp_path / "linear")
    assert len(bundle.tasks) == 5
    assert {task.family for task in bundle.tasks} == {"linear"}
    assert bundle.manifest["families_included"] == ["linear"]
    assert bundle.manifest["counts"]["by_family"] == {"linear": 5}
    assert verify_dataset(bundle) == []


def test_linear_hard_levels(tmp_path):
    profile = DatasetProfile(
        name="linear-hard-test",
        per_cell=1,
        master_seed=731992,
        families=("linear",),
        levels=(6, 7),
    )
    bundle = write_dataset(profile, tmp_path / "linear-hard")
    assert len(bundle.tasks) == 2
    assert [task.level for task in bundle.tasks] == [6, 7]
    assert all(task.family == "linear" for task in bundle.tasks)
    assert bundle.manifest["levels_included"] == [6, 7]
    assert bundle.manifest["counts"]["by_level"] == {"6": 1, "7": 1}
    assert verify_dataset(bundle) == []
    assert len(bundle.tasks[0].answer.split(",")) == 24
    assert len(bundle.tasks[1].answer.split(",")) == 30


def test_linear_ladder_dataset(tmp_path):
    profile = DatasetProfile(
        name="linear-ladder-test",
        per_cell=1,
        master_seed=731992,
        families=("linear",),
        levels=(5, 6, 7),
        prompt_version="linear-ladder-1",
        linear_overrides=((5, 16, 32), (6, 20, 40), (7, 24, 50)),
    )
    bundle = write_dataset(profile, tmp_path / "linear-ladder")
    assert len(bundle.tasks) == 3
    assert [(task.level, task.metadata["n"], task.metadata["coeff_bound"]) for task in bundle.tasks] == [
        (5, 16, 32),
        (6, 20, 40),
        (7, 24, 50),
    ]
    assert all(task.prompt_version == "linear-ladder-1" for task in bundle.tasks)
    assert verify_dataset(bundle) == []
