"""Deterministic seed derivation.

Every task is a pure function of (master_seed, family, level, index, versions).
This is the foundation of the benchmark's reproducibility and of its private
holdout: the generator is public, the master seed is not.
"""

from __future__ import annotations

import hashlib
import random


def derive_seed(
    master_seed: int | str,
    family: str,
    level: int,
    index: int,
    generator_version: str,
    prompt_version: str,
    attempt: int = 0,
) -> int:
    material = "|".join(
        [
            str(master_seed),
            family,
            str(level),
            str(index),
            generator_version,
            prompt_version,
            str(attempt),
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def rng_for(
    master_seed: int | str,
    family: str,
    level: int,
    index: int,
    generator_version: str,
    prompt_version: str,
    attempt: int = 0,
) -> tuple[int, random.Random]:
    seed = derive_seed(
        master_seed,
        family,
        level,
        index,
        generator_version,
        prompt_version,
        attempt,
    )
    return seed, random.Random(seed)


def task_id_for(
    family: str,
    level: int,
    seed: int,
    generator_version: str,
    prompt_version: str,
) -> str:
    material = f"{family}:{level}:{seed}:{generator_version}:{prompt_version}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
