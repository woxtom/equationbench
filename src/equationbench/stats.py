"""Small statistics helpers shared by the scoring code."""

from __future__ import annotations

import math
from collections.abc import Sequence


def percentile(values: Sequence[float], p: float) -> float | None:
    """Linearly interpolated percentile, or ``None`` for no values."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] * (1 - fraction) + ordered[upper] * fraction)
