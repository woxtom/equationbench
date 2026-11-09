"""The task set a run answers, and its integrity hash."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .types import Task, canonical_json, sha256_text


@dataclass
class DatasetBundle:
    path: Path
    tasks: list[Task]
    manifest: dict[str, Any]


def dataset_hash(tasks: Iterable[Task]) -> str:
    payload = [task.to_dict(include_answer=True, include_solution=True) for task in tasks]
    return sha256_text(canonical_json(payload))
