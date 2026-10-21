"""EquationBench: exact large-equation reasoning for language models."""

from __future__ import annotations

__version__ = "1.0.0"
BENCHMARK_NAME = "EquationBench"
DATASET_VERSION = "v1"
GENERATOR_VERSION = "1.0.0"
PROMPT_VERSION = "1.0"
SCORING_VERSION = "1.0"

FAMILIES = (
    "arith",
    "poly",
    "linear",
    "calculus",
    "modular",
    "matrix",
    "recurrence",
)

FAMILY_LABELS = {
    "arith": "Arithmetic",
    "poly": "Polynomial Algebra",
    "linear": "Linear Systems",
    "calculus": "Calculus",
    "modular": "Modular Arithmetic",
    "matrix": "Matrix Algebra",
    "recurrence": "Recurrences",
}

LEVELS = (1, 2, 3, 4, 5)

LEVEL_LABELS = {
    1: "Warm-up",
    2: "Working",
    3: "Hard",
    4: "Very hard",
    5: "Frontier",
    6: "Extreme",
    7: "Beyond",
    8: "Extreme+",
    9: "Beyond+",
}

# The public datasets use levels 1-5. Hard linear profiles may opt into 6-7.
HARD_LEVELS = (6, 7)

# Fixed seeds for the public artifacts. The sealed set uses an unpublished seed.
PUBLIC_DEV_SEED = 20261017
PUBLIC_TEST_SEED = 731992
