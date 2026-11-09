"""EQB v3: effective solved levels on a shared whole-level grid.

Fit valid-task-weighted decreasing isotonic rates, then integrate the piecewise
linear curve in x = 1 + 3 log2(n/3). The score is 1 + area, not normalized by
horizon or task count. Missing grid points are bounded by monotonicity, never
silently filled with successes or failures. Half levels are diagnostics only.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field

from . import SCORING_VERSION
from .frontier import LevelResult, isotonic_decreasing
from .ladder import MAX_PUBLIC_LEVEL, level_for_size, size_for_level
from .stats import percentile
from .types import Level

DEFAULT_HORIZON = 11
DEFAULT_BOOTSTRAP_REPLICATES = 2000
DEFAULT_BOOTSTRAP_SEED = 1729
SCORE_METHOD = "isotonic-whole-level-log-area"


@dataclass
class AreaScore:
    score: float | None
    bounds: tuple[float, float]
    ci: tuple[float, float] | None = None
    censored: str | None = None
    horizon: int = DEFAULT_HORIZON
    horizon_coordinate: float = 0.0
    levels: list[dict] = field(default_factory=list)
    inferred_levels: list[int] = field(default_factory=list)
    unresolved_levels: list[int] = field(default_factory=list)
    ignored_levels: list[Level] = field(default_factory=list)
    method: str = SCORE_METHOD
    scoring_version: str = SCORING_VERSION
    bootstrap_replicates: int = 0
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED
    confidence: float = 0.95

    def to_dict(self) -> dict:
        return asdict(self)


def validate_horizon(horizon: int) -> None:
    if (
        isinstance(horizon, bool)
        or not isinstance(horizon, int)
        or not 2 <= horizon <= MAX_PUBLIC_LEVEL
    ):
        raise ValueError(f"horizon must be an integer in 2..{MAX_PUBLIC_LEVEL}")


def _integral(coordinates: Sequence[float], rates: Sequence[float]) -> float:
    return 1.0 + sum(
        (right - left) * (p + q) / 2
        for left, right, p, q in zip(coordinates, coordinates[1:], rates, rates[1:])
    )


def _fit(
    ordered: Sequence[LevelResult], horizon: int, coordinates: Sequence[float]
) -> tuple[tuple[float, float], list[float], list[int], list[int]]:
    fitted = isotonic_decreasing(
        [result.p for result in ordered], [result.valid for result in ordered]
    )
    observed = {int(result.level): p for result, p in zip(ordered, fitted)}
    lower, upper = [], []
    inferred, unresolved = [], []
    for level in range(1, horizon + 1):
        if level in observed:
            low = high = observed[level]
        else:
            # A missing easier point is at least as good as the next harder
            # observation; a missing harder point is at most as good as the
            # preceding easier observation. These are identification bounds,
            # conditional on the fitted observed rates, not confidence bounds.
            low = next((observed[k] for k in range(level + 1, horizon + 1) if k in observed), 0.0)
            high = next((observed[k] for k in range(level - 1, 0, -1) if k in observed), 1.0)
            (inferred if math.isclose(low, high, abs_tol=1e-12) else unresolved).append(level)
        lower.append(low)
        upper.append(high)
    return (
        (_integral(coordinates, lower), _integral(coordinates, upper)),
        fitted,
        inferred,
        unresolved,
    )


def estimate_area(
    results: Sequence[LevelResult],
    *,
    horizon: int = DEFAULT_HORIZON,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
    confidence: float = 0.95,
) -> AreaScore:
    """Estimate EQB or missing-grid bounds using a shared integration horizon.

    Every whole level from 1 through ``horizon`` is a knot. Unobserved knots
    are identified only when their monotone lower and upper rates coincide.
    A score is ranked only if all knots are identified. Half/out-of-horizon
    levels are reported as ignored and cannot influence fitting or bootstrap.
    """
    validate_horizon(horizon)
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    if bootstrap_replicates < 0:
        raise ValueError("bootstrap_replicates must be non-negative")
    seen = set()
    for result in results:
        if result.level in seen:
            raise ValueError(f"duplicate level: {result.level}")
        seen.add(result.level)
    ordered = sorted(
        (r for r in results if r.valid and float(r.level).is_integer() and 1 <= r.level <= horizon),
        key=lambda r: r.level,
    )
    if not ordered:
        raise ValueError("no valid whole-level outcomes within the scoring horizon")
    coordinates = [level_for_size(size_for_level(level)) for level in range(1, horizon + 1)]
    bounds, fitted, inferred, unresolved = _fit(ordered, horizon, coordinates)
    point = None if unresolved else bounds[0]
    ci = None
    if point is not None and bootstrap_replicates:
        rng = random.Random(bootstrap_seed)
        lows, highs = [], []
        for _ in range(bootstrap_replicates):
            replicate = [
                LevelResult(r.level, tuple(rng.choice(r.outcomes) for _ in r.outcomes))
                for r in ordered
            ]
            rep_bounds, _, _, _ = _fit(replicate, horizon, coordinates)
            # Retain every replicate, including ones with unresolved knots.
            lows.append(rep_bounds[0])
            highs.append(rep_bounds[1])
        alpha = (1 - confidence) / 2
        ci = (percentile(lows, alpha), percentile(highs, 1 - alpha))
    return AreaScore(
        score=point,
        bounds=bounds,
        ci=ci,
        censored="incomplete" if unresolved else None,
        horizon=horizon,
        horizon_coordinate=coordinates[-1],
        levels=[
            {
                "level": r.level,
                "size": size_for_level(r.level),
                "valid": r.valid,
                "correct": r.correct,
                "p": r.p,
                "smoothed": p,
            }
            for r, p in zip(ordered, fitted)
        ],
        inferred_levels=inferred,
        unresolved_levels=unresolved,
        ignored_levels=sorted(
            r.level for r in results if not float(r.level).is_integer() or r.level > horizon
        ),
        bootstrap_replicates=bootstrap_replicates if point is not None else 0,
        bootstrap_seed=bootstrap_seed,
        confidence=confidence,
    )


def estimate_from_counts(
    counts: Mapping[Level, tuple[int, int]],
    *,
    horizon: int = DEFAULT_HORIZON,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
    confidence: float = 0.95,
) -> AreaScore:
    return estimate_area(
        [
            LevelResult.from_counts(level, correct, valid)
            for level, (correct, valid) in counts.items()
        ],
        horizon=horizon,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
        confidence=confidence,
    )
