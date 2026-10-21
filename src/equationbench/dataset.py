"""Dataset construction, serialization, and sealed-holdout support."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from cryptography.fernet import Fernet, InvalidToken

from . import (
    BENCHMARK_NAME,
    HARD_LEVELS,
    DATASET_VERSION,
    FAMILIES,
    FAMILY_LABELS,
    GENERATOR_VERSION,
    LEVELS,
    PROMPT_VERSION,
)
from .generation import FAMILY_DESCRIPTIONS, generate_for
from .rng import rng_for, task_id_for
from .types import Task, canonical_json, sha256_text


@dataclass(frozen=True)
class DatasetProfile:
    name: str
    per_cell: int
    master_seed: int | str
    sealed: bool = False
    description: str = ""
    families: tuple[str, ...] = FAMILIES
    levels: tuple[int, ...] = LEVELS
    prompt_version: str = PROMPT_VERSION
    linear_overrides: tuple[tuple[int, int, int], ...] = ()
    difficulty_overrides: tuple[tuple[int, float], ...] = ()


DEFAULT_PROFILES: dict[str, DatasetProfile] = {
    "dev": DatasetProfile(
        name="dev",
        per_cell=1,
        master_seed=20261017,
        description="Public development set: one task per family/level cell.",
    ),
    "test": DatasetProfile(
        name="test",
        per_cell=2,
        master_seed=731992,
        description="Public evaluation set used for the open leaderboard.",
    ),
    "sealed": DatasetProfile(
        name="sealed",
        per_cell=4,
        master_seed="__random__",
        sealed=True,
        description="Encrypted holdout for official verification and future seasons.",
    ),
    "linear-test": DatasetProfile(
        name="linear-test",
        per_cell=2,
        master_seed=731992,
        families=("linear",),
        description="Public linear-systems-only test set: 2 tasks per level.",
    ),
    "linear-dev": DatasetProfile(
        name="linear-dev",
        per_cell=1,
        master_seed=20261017,
        families=("linear",),
        description="Public linear-systems-only development set.",
    ),
    "linear-hard-test": DatasetProfile(
        name="linear-hard-test",
        per_cell=1,
        master_seed=731992,
        families=("linear",),
        levels=HARD_LEVELS,
        description="Hard linear-systems-only test set: L6 (24x24) and L7 (30x30).",
    ),
    "linear-ladder-test": DatasetProfile(
        name="linear-ladder-test",
        per_cell=1,
        master_seed=731992,
        families=("linear",),
        levels=(5, 6, 7),
        prompt_version="linear-ladder-1",
        linear_overrides=((5, 16, 32), (6, 20, 40), (7, 24, 50)),
        description="Linear size ladder: L5 16x16, L6 20x20, L7 24x24.",
    ),
    "linear-ladder-6": DatasetProfile(
        name="linear-ladder-6",
        per_cell=2,
        master_seed=731992,
        families=("linear",),
        levels=(5, 6, 7),
        prompt_version="linear-ladder-1",
        linear_overrides=((5, 16, 32), (6, 20, 40), (7, 24, 50)),
        description="Two-task linear ladder: two tasks each at 16x16, 20x20, 24x24.",
    ),
    "linear-ladder-10": DatasetProfile(
        name="linear-ladder-10",
        per_cell=2,
        master_seed=731992,
        families=("linear",),
        levels=(5, 8, 6, 9, 7),
        prompt_version="linear-ladder-1",
        linear_overrides=(
            (5, 16, 32),
            (8, 18, 36),
            (6, 20, 40),
            (9, 22, 45),
            (7, 24, 50),
        ),
        difficulty_overrides=((5, 5.0), (8, 5.5), (6, 6.0), (9, 6.5), (7, 7.0)),
        description="Fine linear ladder: two tasks each at 16, 18, 20, 22, and 24 variables.",
    ),
}


@dataclass
class DatasetBundle:
    path: Path
    tasks: list[Task]
    manifest: dict[str, Any]

    @property
    def by_id(self) -> dict[str, Task]:
        return {task.task_id: task for task in self.tasks}


def dataset_hash(tasks: Iterable[Task]) -> str:
    payload = [task.to_dict(include_answer=True, include_solution=True) for task in tasks]
    return sha256_text(canonical_json(payload))


def _task_hash(task: Task) -> str:
    return sha256_text(canonical_json(task.to_dict(include_answer=True, include_solution=True)))


def _counts(
    tasks: Iterable[Task],
    families: Iterable[str] = FAMILIES,
    levels: Iterable[int] = LEVELS,
) -> dict[str, Any]:
    tasks = list(tasks)
    by_family = {family: 0 for family in families}
    by_level = {str(level): 0 for level in levels}
    for task in tasks:
        by_family[task.family] = by_family.get(task.family, 0) + 1
        by_level[str(task.level)] = by_level.get(str(task.level), 0) + 1
    return {"total": len(tasks), "by_family": by_family, "by_level": by_level}


def _resolve_profile(profile: DatasetProfile) -> DatasetProfile:
    if profile.master_seed != "__random__":
        return profile
    seed = secrets.randbits(128)
    return DatasetProfile(
        name=profile.name,
        per_cell=profile.per_cell,
        master_seed=seed,
        sealed=profile.sealed,
        description=profile.description,
        families=profile.families,
        levels=profile.levels,
        prompt_version=profile.prompt_version,
        linear_overrides=profile.linear_overrides,
        difficulty_overrides=profile.difficulty_overrides,
    )


def build_task(
    family: str,
    level: int,
    index: int,
    profile: DatasetProfile,
) -> Task:
    """Generate one deterministic task, retrying only generation failures."""
    last_error: Exception | None = None
    size_override = None
    coeff_override = None
    if family == "linear":
        for override_level, override_n, override_coeff in profile.linear_overrides:
            if override_level == level:
                size_override = override_n
                coeff_override = override_coeff
                break
    for attempt in range(12):
        seed, rng = rng_for(
            profile.master_seed,
            family,
            level,
            index,
            GENERATOR_VERSION,
            profile.prompt_version,
            attempt=attempt,
        )
        try:
            generated = generate_for(
                family,
                level,
                rng,
                n_override=size_override,
                coeff_override=coeff_override,
            )
            difficulty = dict(profile.difficulty_overrides).get(level)
            if difficulty is not None:
                generated = type(generated)(
                    prompt=generated.prompt,
                    answer=generated.answer,
                    answer_type=generated.answer_type,
                    solution=generated.solution,
                    metadata={**generated.metadata, "difficulty": difficulty},
                )
        except Exception as exc:  # pragma: no cover - defense against generator bugs
            last_error = exc
            continue
        task_id = task_id_for(
            family,
            level,
            seed,
            GENERATOR_VERSION,
            profile.prompt_version,
        )
        return Task(
            task_id=task_id,
            family=family,
            level=level,
            seed=seed,
            prompt=generated.prompt,
            answer=generated.answer,
            answer_type=generated.answer_type,
            solution=generated.solution,
            metadata=generated.metadata,
            generator_version=GENERATOR_VERSION,
            prompt_version=profile.prompt_version,
        )
    raise RuntimeError(f"could not generate {family} level {level} index {index}: {last_error}")


def build_tasks(profile: DatasetProfile) -> list[Task]:
    profile = _resolve_profile(profile)
    tasks: list[Task] = []
    for family in profile.families:
        for level in profile.levels:
            for index in range(profile.per_cell):
                tasks.append(build_task(family, level, index, profile))
    return tasks


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _manifest(
    profile: DatasetProfile,
    tasks: list[Task],
    created_at: str,
    *,
    sealed: bool,
) -> dict[str, Any]:
    task_hashes = {task.task_id: _task_hash(task) for task in tasks}
    manifest: dict[str, Any] = {
        "benchmark": BENCHMARK_NAME,
        "benchmark_version": "1.0.0",
        "dataset_version": DATASET_VERSION,
        "generator_version": GENERATOR_VERSION,
        "prompt_version": profile.prompt_version,
        "name": profile.name,
        "description": profile.description,
        "sealed": sealed,
        "per_cell": profile.per_cell,
        "created_at": created_at,
        "counts": _counts(tasks, profile.families, profile.levels),
        "dataset_sha256": dataset_hash(tasks),
        "task_hashes": task_hashes,
        "families_included": list(profile.families),
        "levels_included": list(profile.levels),
        "linear_overrides": list(profile.linear_overrides),
        "difficulty_overrides": list(profile.difficulty_overrides),
        "families": {
            family: {
                "label": FAMILY_LABELS[family],
                "description": FAMILY_DESCRIPTIONS[family],
                "levels": len(profile.levels),
                "per_cell": profile.per_cell,
            }
            for family in profile.families
        },
    }
    if sealed:
        manifest["master_seed_sha256"] = hashlib.sha256(
            str(profile.master_seed).encode("utf-8")
        ).hexdigest()
        manifest["encryption"] = "fernet-aes128-cbc-hmac-sha256"
    else:
        manifest["master_seed"] = profile.master_seed
    return manifest


def _key_from_env() -> str | None:
    return os.environ.get("EQB_SEALED_KEY")


def get_or_create_key(path: Path) -> str:
    env_key = _key_from_env()
    if env_key:
        return env_key
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    key = Fernet.generate_key().decode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def encrypt_payload(payload: bytes, key: str) -> bytes:
    return Fernet(key.encode("ascii")).encrypt(payload)


def decrypt_payload(payload: bytes, key: str) -> bytes:
    try:
        return Fernet(key.encode("ascii")).decrypt(payload)
    except InvalidToken as exc:
        raise ValueError("sealed dataset key is invalid or the file is corrupted") from exc


def write_dataset(
    profile: DatasetProfile,
    out_dir: Path,
    *,
    key_file: Path | None = None,
    seed_file: Path | None = None,
) -> DatasetBundle:
    profile = _resolve_profile(profile)
    tasks = build_tasks(profile)
    out_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest = _manifest(profile, tasks, created_at, sealed=profile.sealed)

    if profile.sealed:
        key_path = key_file or Path(".secrets/sealed.key")
        key = get_or_create_key(key_path)
        payload = canonical_json(
            [task.to_dict(include_answer=True, include_solution=True) for task in tasks]
        ).encode("utf-8")
        encrypted = encrypt_payload(payload, key)
        (out_dir / "sealed.enc").write_bytes(encrypted)
        if seed_file is not None:
            seed_file.parent.mkdir(parents=True, exist_ok=True)
            seed_file.write_text(str(profile.master_seed) + "\n", encoding="utf-8")
            try:
                os.chmod(seed_file, 0o600)
            except OSError:
                pass
        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (out_dir / "README.md").write_text(
            _sealed_readme(manifest, out_dir), encoding="utf-8"
        )
        return DatasetBundle(path=out_dir, tasks=tasks, manifest=manifest)

    _write_jsonl(
        out_dir / "tasks.jsonl",
        (task.to_dict(include_answer=True, include_solution=True) for task in tasks),
    )
    _write_jsonl(
        out_dir / "prompts.jsonl",
        (task.public_dict() for task in tasks),
    )
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "README.md").write_text(_public_readme(manifest, out_dir), encoding="utf-8")
    return DatasetBundle(path=out_dir, tasks=tasks, manifest=manifest)


def load_dataset(path: Path, key: str | None = None, key_file: Path | None = None) -> DatasetBundle:
    path = Path(path)
    if path.is_file() and path.suffix == ".jsonl":
        path = path.parent
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"no manifest.json in {path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if (path / "tasks.jsonl").exists():
        tasks = [
            Task.from_dict(json.loads(line))
            for line in (path / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    elif (path / "sealed.enc").exists():
        if key is None:
            key_path = key_file or Path(".secrets/sealed.key")
            if key_path.exists():
                key = key_path.read_text(encoding="utf-8").strip()
            else:
                raise ValueError(
                    "this is a sealed dataset; provide --key, EQB_SEALED_KEY, or a key file"
                )
        plaintext = decrypt_payload((path / "sealed.enc").read_bytes(), key)
        rows = json.loads(plaintext.decode("utf-8"))
        tasks = [Task.from_dict(row) for row in rows]
    else:
        raise FileNotFoundError(f"no tasks.jsonl or sealed.enc in {path}")

    return DatasetBundle(path=path, tasks=tasks, manifest=manifest)


def verify_dataset(bundle: DatasetBundle, *, regenerate: bool = True) -> list[str]:
    """Return a list of integrity problems (empty means healthy)."""
    problems: list[str] = []
    tasks = bundle.tasks
    seen: set[str] = set()
    for task in tasks:
        if task.task_id in seen:
            problems.append(f"duplicate task id: {task.task_id}")
        seen.add(task.task_id)
        if task.task_id != task_id_for(
            task.family, task.level, task.seed, task.generator_version, task.prompt_version
        ):
            problems.append(f"task id does not match seed: {task.task_id}")
        if regenerate:
            import random

            n_override = task.metadata.get("n") if task.family == "linear" else None
            coeff_override = (
                task.metadata.get("coeff_bound") if task.family == "linear" else None
            )
            generated = generate_for(
                task.family,
                task.level,
                random.Random(task.seed),
                n_override=n_override,
                coeff_override=coeff_override,
            )
            if generated.answer != task.answer:
                problems.append(f"answer mismatch after regeneration: {task.task_id}")
            if generated.prompt != task.prompt:
                problems.append(f"prompt mismatch after regeneration: {task.task_id}")
    if bundle.manifest.get("dataset_sha256") != dataset_hash(tasks):
        problems.append("dataset_sha256 does not match task contents")
    expected = bundle.manifest.get("counts", {}).get("total")
    if expected != len(tasks):
        problems.append(f"manifest count {expected} != actual count {len(tasks)}")
    return problems


def _public_readme(manifest: dict[str, Any], out_dir: Path) -> str:
    counts = manifest["counts"]
    family_lines = "\n".join(
        f"| `{family}` | {FAMILY_LABELS[family]} | {counts['by_family'][family]} |"
        for family in counts["by_family"]
    )
    return f"""# EquationBench {manifest['dataset_version']} — {manifest['name']} set

{manifest.get('description', '')}

- Tasks: **{counts['total']}** ({manifest['per_cell']} per family × level)
- Dataset hash: `{manifest['dataset_sha256']}`
- Master seed: `{manifest.get('master_seed', 'hidden')}`
- Generator: `{manifest['generator_version']}` · Prompt: `{manifest['prompt_version']}`

| Family | Track | Tasks |
|---|---|---:|
{family_lines}

`tasks.jsonl` includes answers and short solutions. `prompts.jsonl` is the
model-facing subset. The private holdout is generated separately from an
unpublished seed and is not in this directory.
"""


def _sealed_readme(manifest: dict[str, Any], out_dir: Path) -> str:
    return f"""# EquationBench {manifest['dataset_version']} — sealed holdout

This directory contains an encrypted holdout. The key is **not** in the
repository. Do not publish decrypted tasks or answers.

- Tasks: **{manifest['counts']['total']}**
- Plaintext hash commitment: `{manifest['dataset_sha256']}`
- Seed commitment: `{manifest['master_seed_sha256']}`
- File: `sealed.enc`

Use `eqb dataset decrypt --path {out_dir} --out /tmp/eqb-sealed` with
`EQB_SEALED_KEY` or a local key file to evaluate a model. After the season,
publish the key and the plaintext task file so the commitment can be verified.
"""
