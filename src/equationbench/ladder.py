"""Open-ended linear-system ladder.

The ladder is geometric: each level is a constant step in ``log n``, so a
frontier score expressed in levels is also a constant step in the log of the
system size.  Levels are unbounded in principle; ``size_for_level`` simply
rounds the ideal geometric size to an integer.

The public task bank is deterministic from ``(season_seed, level, index)``.
That makes every level reproducible without shipping a huge fixed dataset.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from . import GENERATOR_VERSION, PROMPT_VERSION
from .generation.linear import generate_size
from .rng import rng_for, task_id_for
from .types import Task

LADDER_VERSION = "1"
LADDER_GENERATOR_VERSION = f"{GENERATOR_VERSION}+ladder{LADDER_VERSION}"

#: The ladder starts at a 3x3 system.  Level 1 is deliberately easy.
BASE_SIZE = 3

#: One geometric step.  Three levels double the system size.
LEVEL_STEP = 2 ** (1 / 3)

#: One difficulty axis only: size.  These bounds are fixed for the season.
COEFF_BOUND = 30
X_BOUND = 9

#: Core bank + precision bank used at the two bracket levels.
TASKS_PER_LEVEL = 5
PRECISION_TASKS = 5

#: Public season seed.  It is not secret; the sealed holdout uses another seed.
DEFAULT_SEASON_SEED = 731992

#: Levels 1..17 fit a ~32k-token prompt budget.  Levels above this are
#: long-context extensions rather than part of the default public protocol.
OFFICIAL_CAP_LEVEL = 17
MAX_PUBLIC_LEVEL = 20


def ideal_size_for_level(level: float) -> float:
    """Continuous geometric size for a (possibly fractional) level."""
    if level < 1:
        raise ValueError(f"level must be at least 1, got {level}")
    return BASE_SIZE * LEVEL_STEP ** (level - 1)


def size_for_level(level: int) -> int:
    """Return the integer system size ``n`` for a ladder level.

    ``level`` must be >= 1.  The result is rounded to the nearest integer, so
    adjacent levels are always strictly increasing for the levels shipped in
    the public protocol.
    """
    if level < 1:
        raise ValueError(f"level must be at least 1, got {level}")
    return max(2, round(ideal_size_for_level(level)))


def level_for_size(size: float) -> float:
    """Continuous inverse of the ideal geometric ladder.

    This is useful for displaying a frontier size as a level.  It is not the
    inverse of the rounded ``size_for_level`` mapping; use the actual integer
    sizes when interpolating a measured curve.
    """
    if size <= 0:
        raise ValueError(f"size must be positive, got {size}")
    return 1 + 3 * math.log2(size / BASE_SIZE)


def estimate_prompt_chars(size: int) -> int:
    """Approximate prompt size before a task is generated.

    The linear prompt is dominated by ``n^2`` coefficient terms.  The fit is
    deliberately conservative; ``eqb ladder --measure`` prints measured sizes.
    """
    return max(1, round(8.5 * size * size + 20 * size + 500))


def estimate_prompt_tokens(size: int) -> int:
    """Rough token estimate at four characters per token."""
    return max(1, round(estimate_prompt_chars(size) / 4))


def build_ladder_task(
    level: int,
    index: int,
    *,
    season_seed: int | str = DEFAULT_SEASON_SEED,
    coeff_bound: int = COEFF_BOUND,
    x_bound: int = X_BOUND,
) -> Task:
    """Generate one deterministic task at a ladder level.

    ``index`` is zero-based.  Indices 0..4 are the core bank; indices 5..9 are
    the precision bank used at the bracket levels.
    """
    if index < 0:
        raise ValueError(f"task index must be non-negative, got {index}")
    size = size_for_level(level)
    seed, rng = rng_for(
        season_seed,
        "linear",
        level,
        index,
        LADDER_GENERATOR_VERSION,
        PROMPT_VERSION,
    )
    generated = generate_size(
        size,
        rng,
        coeff_bound=coeff_bound,
        x_bound=x_bound,
    )
    task_id = task_id_for(
        "linear",
        level,
        seed,
        LADDER_GENERATOR_VERSION,
        PROMPT_VERSION,
    )
    metadata = {
        **generated.metadata,
        "ladder_version": LADDER_VERSION,
        "ladder_level": level,
        "level_size": size,
        "task_index": index + 1,
    }
    return Task(
        task_id=task_id,
        family="linear",
        level=level,
        seed=seed,
        prompt=generated.prompt,
        answer=generated.answer,
        answer_type=generated.answer_type,
        solution=generated.solution,
        metadata=metadata,
        generator_version=LADDER_GENERATOR_VERSION,
        prompt_version=PROMPT_VERSION,
    )


def build_level_tasks(
    level: int,
    count: int = TASKS_PER_LEVEL,
    *,
    start_index: int = 0,
    season_seed: int | str = DEFAULT_SEASON_SEED,
    coeff_bound: int = COEFF_BOUND,
    x_bound: int = X_BOUND,
) -> list[Task]:
    """Generate ``count`` tasks at one level, starting at ``start_index``."""
    if count < 1:
        raise ValueError(f"count must be positive, got {count}")
    return [
        build_ladder_task(
            level,
            start_index + offset,
            season_seed=season_seed,
            coeff_bound=coeff_bound,
            x_bound=x_bound,
        )
        for offset in range(count)
    ]


def build_bank(
    levels: Iterable[int],
    *,
    tasks_per_level: int = TASKS_PER_LEVEL,
    precision_tasks: int = PRECISION_TASKS,
    season_seed: int | str = DEFAULT_SEASON_SEED,
    coeff_bound: int = COEFF_BOUND,
    x_bound: int = X_BOUND,
) -> list[Task]:
    """Build the core + precision bank for a range of levels."""
    tasks: list[Task] = []
    for level in levels:
        tasks.extend(
            build_level_tasks(
                level,
                tasks_per_level + precision_tasks,
                season_seed=season_seed,
                coeff_bound=coeff_bound,
                x_bound=x_bound,
            )
        )
    return tasks


def ladder_rows(
    max_level: int = MAX_PUBLIC_LEVEL,
    *,
    official_cap: int = OFFICIAL_CAP_LEVEL,
) -> list[dict]:
    """Rows for the human-readable ladder table."""
    if max_level < 1:
        raise ValueError(f"max_level must be at least 1, got {max_level}")
    rows = []
    for level in range(1, max_level + 1):
        size = size_for_level(level)
        rows.append(
            {
                "level": level,
                "size": size,
                "approx_prompt_chars": estimate_prompt_chars(size),
                "approx_prompt_tokens": estimate_prompt_tokens(size),
                "tasks_per_level": TASKS_PER_LEVEL,
                "precision_tasks": PRECISION_TASKS,
                "zone": "core" if level <= official_cap else "extension",
            }
        )
    return rows


def ladder_manifest(
    max_level: int = MAX_PUBLIC_LEVEL,
    *,
    official_cap: int = OFFICIAL_CAP_LEVEL,
    season_seed: int | str = DEFAULT_SEASON_SEED,
) -> dict:
    """Machine-readable description of the public ladder."""
    return {
        "ladder_version": LADDER_VERSION,
        "generator_version": LADDER_GENERATOR_VERSION,
        "prompt_version": PROMPT_VERSION,
        "formula": "round(3 * 2 ** ((level - 1) / 3))",
        "base_size": BASE_SIZE,
        "coefficient_bound": COEFF_BOUND,
        "solution_bound": X_BOUND,
        "tasks_per_level": TASKS_PER_LEVEL,
        "precision_tasks": PRECISION_TASKS,
        "official_cap_level": official_cap,
        "max_public_level": max_level,
        "season_seed": season_seed if isinstance(season_seed, int) else "<string>",
        "levels": ladder_rows(max_level, official_cap=official_cap),
    }


__all__ = [
    "BASE_SIZE",
    "COEFF_BOUND",
    "DEFAULT_SEASON_SEED",
    "LADDER_GENERATOR_VERSION",
    "LADDER_VERSION",
    "MAX_PUBLIC_LEVEL",
    "OFFICIAL_CAP_LEVEL",
    "PRECISION_TASKS",
    "TASKS_PER_LEVEL",
    "X_BOUND",
    "build_bank",
    "build_ladder_task",
    "build_level_tasks",
    "estimate_prompt_chars",
    "estimate_prompt_tokens",
    "ideal_size_for_level",
    "ladder_manifest",
    "ladder_rows",
    "level_for_size",
    "size_for_level",
]
