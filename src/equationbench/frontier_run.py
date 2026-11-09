"""Compatibility imports for pre-v3 scripts; new runs use EQB area scoring.

Use :mod:`equationbench.ladder_run` in new code. Historical frontier artifacts
are not rewritten; the current runner writes ``eqb.json``.
"""

from .ladder_run import (
    area_from_predictions as frontier_from_predictions,
)
from .ladder_run import (
    build_ladder_bundle,
    bundle_from_receipt,
)
from .ladder_run import (
    run_ladder as run_frontier,
)

__all__ = [
    "build_ladder_bundle",
    "bundle_from_receipt",
    "frontier_from_predictions",
    "run_frontier",
]
