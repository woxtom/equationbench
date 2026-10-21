"""EquationBench: exact linear-system reasoning on an open-ended ladder."""

from __future__ import annotations

__version__ = "2.0.0"
BENCHMARK_NAME = "EquationBench"
DATASET_VERSION = "v2"
GENERATOR_VERSION = "2.0.0"
PROMPT_VERSION = "1.0"
SCORING_VERSION = "1.0"
FRONTIER_SCORING_VERSION = "2.0"

FAMILIES = ("linear",)

FAMILY_LABELS = {"linear": "Linear Systems"}

LEVELS = (1, 2, 3, 4, 5)

LEVEL_LABELS = {
    1: "Warm-up",
    2: "Working",
    3: "Hard",
    4: "Very hard",
    5: "Frontier",
}

# Fixed seeds for the legacy fixed-set artifacts. The open-ended ladder has its
# own season seed in equationbench.ladder.
PUBLIC_DEV_SEED = 20261017
PUBLIC_TEST_SEED = 731992
