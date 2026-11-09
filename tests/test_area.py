"""Scoring v3: geometry, identification bounds, and monotonic ranking."""

from __future__ import annotations

import itertools
import json

import pytest

from equationbench.area import DEFAULT_HORIZON, estimate_area, estimate_from_counts
from equationbench.frontier import LevelResult
from equationbench.ladder import level_for_size, size_for_level


def x(level):
    return level_for_size(size_for_level(level))


def score(counts, **kwargs):
    return estimate_from_counts(counts, bootstrap_replicates=0, **kwargs)


def test_area_is_trapezoidal_in_actual_log_sizes():
    result = score({1: (5, 5), 2: (3, 5), 3: (0, 5)})
    expected = 1 + (x(2) - x(1)) * 0.8 + (x(3) - x(2)) * 0.3
    assert result.score == pytest.approx(expected)
    assert result.bounds == pytest.approx((expected, expected))
    assert result.inferred_levels == list(range(4, DEFAULT_HORIZON + 1))
    assert result.censored is None


def test_missing_endpoints_are_inferred_only_on_identified_plateaus():
    result = score({3: (5, 5), 4: (0, 5)})
    assert result.score == pytest.approx((x(3) + x(4)) / 2)
    assert result.inferred_levels == [1, 2, *range(5, DEFAULT_HORIZON + 1)]
    assert not result.unresolved_levels


def test_missing_easy_levels_produce_bounds_not_a_ranked_score():
    result = score({3: (4, 5), 4: (2, 5), 5: (0, 5), 6: (0, 5)})
    assert result.score is None
    assert result.ci is None
    assert result.censored == "incomplete"
    assert result.unresolved_levels == [1, 2]
    assert result.bounds[0] == pytest.approx(3.4912018560670304)
    assert result.bounds[0] < result.bounds[1]


def test_missing_internal_level_is_not_silently_interpolated():
    result = score({1: (5, 5), 3: (0, 5)})
    assert result.score is None
    assert result.unresolved_levels == [2]
    assert result.bounds[0] == pytest.approx(1 + (x(2) - 1) / 2)
    assert result.bounds[1] == pytest.approx(x(2) + (x(3) - x(2)) / 2)
    # Empty levels and absent levels mean the same thing.
    assert score({1: (5, 5), 2: (0, 0), 3: (0, 5)}).bounds == result.bounds


def test_missing_internal_plateau_is_identified():
    result = score({1: (5, 5), 3: (5, 5), 4: (0, 5)})
    assert result.score is not None
    assert 2 in result.inferred_levels


def test_partial_all_pass_has_bounds_full_horizon_all_pass_is_ceiling():
    partial = score({1: (5, 5), 2: (5, 5)})
    assert partial.score is None
    assert partial.bounds[1] == x(DEFAULT_HORIZON)
    complete = score({level: (5, 5) for level in range(1, DEFAULT_HORIZON + 1)})
    assert complete.score == x(DEFAULT_HORIZON)


def test_all_fail_from_l1_is_baseline_not_a_missing_score():
    assert score({1: (0, 5)}).score == 1
    assert score({3: (0, 5)}).score is None


def test_half_levels_and_out_of_horizon_levels_do_not_change_score_or_ci():
    counts = {9: (5, 5), 10: (3, 5), 11: (0, 5)}
    a = estimate_from_counts(counts, bootstrap_replicates=100)
    b = estimate_from_counts(
        {**counts, 9.5: (0, 10), 10.5: (10, 10), 12: (5, 5)}, bootstrap_replicates=100
    )
    assert a.score == b.score
    assert a.ci == b.ci
    assert b.ignored_levels == [9.5, 10.5, 12]


def test_extra_trials_are_not_integration_weights():
    a = score({1: (5, 5), 2: (3, 5), 3: (0, 5)})
    b = score({1: (5, 5), 2: (6, 10), 3: (0, 5)})
    assert a.score == b.score


def test_adding_zero_tail_and_extending_horizon_does_not_dilute_score():
    counts = {1: (5, 5), 2: (3, 5), 3: (0, 5)}
    a = score(counts, horizon=3)
    b = score({**counts, 4: (0, 5), 5: (0, 5)}, horizon=15)
    assert a.score == b.score


def test_every_improvement_is_non_decreasing_on_fixed_grid():
    # Exhaustively includes isotonic pooling and curves crossing 50%.
    for values in itertools.product(range(3), repeat=4):
        counts = {level: (correct, 2) for level, correct in enumerate(values, 1)}
        before = score(counts, horizon=4).score
        for level, (correct, total) in counts.items():
            if correct == total:
                continue
            after = score({**counts, level: (correct + 1, total)}, horizon=4).score
            assert after >= before - 1e-12


def test_noise_is_pooled_and_bootstrap_reproducible():
    counts = {1: (5, 5), 2: (1, 5), 3: (4, 5), 4: (0, 5)}
    a = estimate_from_counts(counts, bootstrap_replicates=100, bootstrap_seed=9)
    b = estimate_from_counts(counts, bootstrap_replicates=100, bootstrap_seed=9)
    assert a.levels[1]["smoothed"] == 0.5
    assert a.levels[2]["smoothed"] == 0.5
    assert a.ci == b.ci
    assert a.ci[0] < a.score < a.ci[1]
    assert json.loads(json.dumps(a.to_dict()))["scoring_version"] == "3.0"


def test_bootstrap_keeps_replicates_with_unresolved_internal_knots():
    # Point-fit rates at L2/L4 coincide, identifying missing L3. Resamples
    # can separate them; their lower/upper areas must not be discarded.
    counts = {1: (5, 5), 2: (2, 4), 4: (2, 4), 5: (0, 5)}
    result = estimate_from_counts(counts, bootstrap_replicates=200, bootstrap_seed=17)
    assert result.score is not None
    assert result.inferred_levels[0] == 3
    assert result.ci is not None
    assert result.ci[0] < result.score < result.ci[1]
    assert result.bootstrap_replicates == 200
    assert result.bootstrap_seed == 17
    assert result.confidence == 0.95


def test_unresolved_runs_do_not_get_fake_confidence_intervals():
    result = estimate_from_counts({5: (3, 5)}, bootstrap_replicates=100)
    assert result.score is None
    assert result.ci is None


@pytest.mark.parametrize("horizon", [0, 1, 1.5, True, 99])
def test_invalid_horizons(horizon):
    with pytest.raises(ValueError, match="horizon"):
        score({1: (1, 1)}, horizon=horizon)


def test_invalid_inputs():
    with pytest.raises(ValueError, match="no valid"):
        score({})
    with pytest.raises(ValueError, match="no valid"):
        score({9.5: (5, 5)})
    with pytest.raises(ValueError, match="duplicate"):
        estimate_area([LevelResult.from_counts(1, 1, 1)] * 2)
    with pytest.raises(ValueError, match="confidence"):
        score({1: (1, 1)}, confidence=1)
    with pytest.raises(ValueError, match="non-negative"):
        estimate_from_counts({1: (1, 1)}, bootstrap_replicates=-1)
