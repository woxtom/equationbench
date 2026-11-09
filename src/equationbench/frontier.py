"""Legacy v2 frontier estimator, retained for reproducing historical results.

Current runs and leaderboards use :mod:`equationbench.area` (scoring v3).

The score is the continuous ladder level at which a model has a 50% chance of
solving an exact system.  It is *not* a fraction of a fixed test set, so adding
higher levels does not dilute or cap the score.

Pipeline:

1. collect per-level outcomes,
2. smooth the success curve with a non-increasing isotonic regression,
3. find the adjacent levels that bracket 50%,
4. interpolate in the log of the real integer system sizes,
5. bootstrap tasks within each level for a confidence interval.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from . import FRONTIER_SCORING_VERSION
from .ladder import ideal_size_for_level, level_for_size, size_for_level
from .stats import percentile
from .types import Level

FRONTIER_THRESHOLD = 0.5
DEFAULT_BOOTSTRAP_REPLICATES = 2000
DEFAULT_BOOTSTRAP_SEED = 1729
SCORE_METHOD = "isotonic-log-interpolation"
SCORING_VERSION = FRONTIER_SCORING_VERSION


@dataclass(frozen=True)
class LevelResult:
    """Outcomes for one ladder level.

    ``outcomes`` is the source of truth.  ``from_counts`` expands counts into a
    tuple of booleans so bootstrap resampling is straightforward.
    """

    level: Level
    outcomes: tuple[bool, ...]

    def __post_init__(self) -> None:
        if self.level < 1:
            raise ValueError(f"level must be at least 1, got {self.level}")

    @property
    def valid(self) -> int:
        return len(self.outcomes)

    @property
    def correct(self) -> int:
        return sum(self.outcomes)

    @property
    def p(self) -> float:
        return self.correct / self.valid if self.valid else 0.0

    @classmethod
    def from_counts(cls, level: Level, correct: int, valid: int) -> LevelResult:
        if valid < 0:
            raise ValueError(f"valid must be non-negative, got {valid}")
        if correct < 0 or correct > valid:
            raise ValueError(f"correct must be in [0, {valid}], got {correct}")
        return cls(level=level, outcomes=(True,) * correct + (False,) * (valid - correct))

    @classmethod
    def from_outcomes(cls, level: Level, outcomes: Iterable[bool]) -> LevelResult:
        return cls(level=level, outcomes=tuple(bool(item) for item in outcomes))


@dataclass
class FrontierScore:
    """Result of frontier estimation.

    ``score`` is ``L*`` when the 50% point is bracketed.  If the model passed
    every attempted level, ``score`` is ``None`` and ``censored == "upper"``;
    ``bound`` is then a lower bound on the true level.  If it failed the first
    level, ``censored == "lower"`` and ``bound`` is an upper bound.
    """

    score: float | None
    size: float | None
    ci: tuple[float, float] | None
    size_ci: tuple[float, float] | None
    censored: str | None
    bound: float | None
    bound_size: float | None
    levels: list[dict] = field(default_factory=list)
    method: str = SCORE_METHOD
    scoring_version: str = SCORING_VERSION
    bootstrap_replicates: int = 0

    @property
    def is_finite(self) -> bool:
        return self.score is not None

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "size": self.size,
            "ci": list(self.ci) if self.ci else None,
            "size_ci": list(self.size_ci) if self.size_ci else None,
            "censored": self.censored,
            "bound": self.bound,
            "bound_size": self.bound_size,
            "levels": self.levels,
            "method": self.method,
            "scoring_version": self.scoring_version,
            "bootstrap_replicates": self.bootstrap_replicates,
        }


@dataclass(frozen=True)
class _Estimate:
    score: float | None
    size: float | None
    censored: str | None
    bound: float | None


def isotonic_decreasing(
    values: Sequence[float], weights: Sequence[float] | None = None
) -> list[float]:
    """Pool-adjacent-violators fit of a non-increasing sequence.

    This is the only smoothing step.  It prevents a lucky high-level solve from
    moving the frontier above a level where the model clearly fails.
    """
    if weights is None:
        weights = [1.0] * len(values)
    if len(values) != len(weights):
        raise ValueError("values and weights must have the same length")
    if not values:
        return []

    blocks: list[list[float]] = []  # [mean, weight, count]
    for value, weight in zip(values, weights):
        if weight <= 0:
            raise ValueError("isotonic weights must be positive")
        blocks.append([float(value), float(weight), 1.0])
        while len(blocks) >= 2 and blocks[-2][0] < blocks[-1][0]:
            mean_b, weight_b, count_b = blocks.pop()
            mean_a, weight_a, count_a = blocks.pop()
            total_weight = weight_a + weight_b
            blocks.append(
                [
                    (mean_a * weight_a + mean_b * weight_b) / total_weight,
                    total_weight,
                    count_a + count_b,
                ]
            )

    fitted: list[float] = []
    for mean, _weight, count in blocks:
        fitted.extend([mean] * int(count))
    return fitted


def _estimate_at(size: float, censored: str | None, bound: float | None) -> _Estimate:
    return _Estimate(score=level_for_size(size), size=size, censored=censored, bound=bound)


def _estimate_from_curve(
    levels: Sequence[Level], smoothed: Sequence[float]
) -> _Estimate:
    """Locate the 50% crossing.

    Rounding makes the ladder uneven: L2 is 4 variables where the ideal size is
    3.78, and L11 is 30 where it is 30.24.  The crossing is therefore found in
    the sizes the model was actually given, then labelled on the continuous
    ``1 + 3 * log2(n / 3)`` scale.
    """
    if not levels:
        raise ValueError("no levels supplied")
    if len(levels) != len(smoothed):
        raise ValueError("levels and smoothed curve must have the same length")
    sizes = [size_for_level(level) for level in levels]

    # Below the first level: only a lower bound is available.
    if smoothed[0] < FRONTIER_THRESHOLD:
        return _Estimate(
            score=None,
            size=None,
            censored="lower",
            bound=float(levels[0]),
        )

    # Flat 50% curve: the threshold is everywhere and nowhere.
    if all(abs(value - FRONTIER_THRESHOLD) < 1e-12 for value in smoothed):
        return _estimate_at(math.sqrt(sizes[0] * sizes[-1]), "ambiguous", None)

    for index in range(len(levels) - 1):
        upper = smoothed[index]
        lower = smoothed[index + 1]
        if upper >= FRONTIER_THRESHOLD > lower:
            span = upper - lower
            fraction = (upper - FRONTIER_THRESHOLD) / span if span else 0.0
            fraction = min(1.0, max(0.0, fraction))
            # Geometric form of the log interpolation: a crossing exactly on a
            # tested size must stay exact, because the band window compares
            # the score against whole levels.
            size = sizes[index] * (sizes[index + 1] / sizes[index]) ** fraction
            return _estimate_at(size, None, None)

    # Every tested level is at or above the threshold.
    if abs(smoothed[-1] - FRONTIER_THRESHOLD) < 1e-12:
        # A final 0.5 plateau can span several levels when isotonic regression
        # pools a noisy last pair (e.g. 2/5 then 3/5).  The crossing is not
        # identified inside the plateau, so report its midpoint rather than
        # pretending the model cleared the final level.
        start = len(smoothed) - 1
        while start > 0 and abs(smoothed[start - 1] - FRONTIER_THRESHOLD) < 1e-12:
            start -= 1
        bound = float(levels[-1])
        if start < len(smoothed) - 1:
            return _estimate_at(math.sqrt(sizes[start] * sizes[-1]), "ambiguous", bound)
        return _estimate_at(float(sizes[-1]), "upper", bound)
    return _Estimate(
        score=None,
        size=None,
        censored="upper",
        bound=float(levels[-1]),
    )


def _fit_curve(results: Sequence[LevelResult]) -> tuple[list[Level], list[float], list[float]]:
    ordered = sorted((result for result in results if result.valid > 0), key=lambda r: r.level)
    if not ordered:
        raise ValueError("no level has a valid outcome")
    levels = [result.level for result in ordered]
    raw = [result.p for result in ordered]
    weights = [float(result.valid) for result in ordered]
    smoothed = isotonic_decreasing(raw, weights)
    return levels, raw, smoothed


def _level_payload(results: Sequence[LevelResult], smoothed: Sequence[float]) -> list[dict]:
    ordered = sorted((result for result in results if result.valid > 0), key=lambda r: r.level)
    payload = []
    for result, fit in zip(ordered, smoothed):
        payload.append(
            {
                "level": result.level,
                "size": size_for_level(result.level),
                "valid": result.valid,
                "correct": result.correct,
                "p": result.p,
                "smoothed": fit,
            }
        )
    return payload


def estimate_frontier(
    results: Sequence[LevelResult],
    *,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
    confidence: float = 0.95,
) -> FrontierScore:
    """Estimate the 50% frontier and a task-level bootstrap interval."""
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    levels, _raw, smoothed = _fit_curve(results)
    point = _estimate_from_curve(levels, smoothed)

    ci: tuple[float, float] | None = None
    size_ci: tuple[float, float] | None = None
    if bootstrap_replicates > 0:
        ordered = sorted(
            (result for result in results if result.valid > 0), key=lambda r: r.level
        )
        rng = random.Random(bootstrap_seed)
        samples: list[float] = []
        for _ in range(bootstrap_replicates):
            replicate: list[LevelResult] = []
            for result in ordered:
                draws = tuple(
                    rng.choice(result.outcomes) for _ in range(result.valid)
                )
                replicate.append(LevelResult(level=result.level, outcomes=draws))
            try:
                rep_levels, _rep_raw, rep_smoothed = _fit_curve(replicate)
                estimate = _estimate_from_curve(rep_levels, rep_smoothed)
            except ValueError:
                continue
            if estimate.score is not None:
                samples.append(estimate.score)

        # Only report an interval when most replicates found a bracket.  A
        # heavily censored run should show a bound, not a fake narrow CI.
        if len(samples) >= max(20, int(0.5 * bootstrap_replicates)):
            alpha = (1 - confidence) / 2
            low = percentile(samples, alpha)
            high = percentile(samples, 1 - alpha)
            if low is not None and high is not None:
                ci = (low, high)
                size_ci = (
                    ideal_size_for_level(low),
                    ideal_size_for_level(high),
                )

    return FrontierScore(
        score=point.score,
        size=point.size,
        ci=ci,
        size_ci=size_ci,
        censored=point.censored,
        bound=point.bound,
        bound_size=float(size_for_level(point.bound)) if point.bound is not None else None,
        levels=_level_payload(results, smoothed),
        bootstrap_replicates=bootstrap_replicates,
    )


def estimate_from_counts(
    counts: Mapping[Level, tuple[int, int]],
    *,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
    confidence: float = 0.95,
) -> FrontierScore:
    """Convenience wrapper: ``{level: (correct, valid)}``."""
    results = [
        LevelResult.from_counts(level, correct, valid)
        for level, (correct, valid) in counts.items()
    ]
    return estimate_frontier(
        results,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
        confidence=confidence,
    )


def estimate_from_outcomes(
    outcomes: Mapping[Level, Sequence[bool]],
    *,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
    confidence: float = 0.95,
) -> FrontierScore:
    """Convenience wrapper: ``{level: [True, False, ...]}``."""
    results = [
        LevelResult.from_outcomes(level, values)
        for level, values in outcomes.items()
    ]
    return estimate_frontier(
        results,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
        confidence=confidence,
    )


__all__ = [
    "DEFAULT_BOOTSTRAP_REPLICATES",
    "DEFAULT_BOOTSTRAP_SEED",
    "FRONTIER_THRESHOLD",
    "SCORE_METHOD",
    "SCORING_VERSION",
    "FrontierScore",
    "LevelResult",
    "estimate_from_counts",
    "estimate_from_outcomes",
    "estimate_frontier",
    "ideal_size_for_level",
    "isotonic_decreasing",
]
