from __future__ import annotations

import json

import pytest

from equationbench.frontier import (
    LevelResult,
    estimate_from_counts,
    estimate_from_outcomes,
    estimate_frontier,
    ideal_size_for_level,
    isotonic_decreasing,
)


def test_isotonic_decreasing_pools_violations():
    assert isotonic_decreasing([1.0, 0.0, 1.0, 0.0]) == pytest.approx(
        [1.0, 0.5, 0.5, 0.0]
    )
    assert isotonic_decreasing([1.0, 0.0, 1.0], [1.0, 1.0, 4.0]) == pytest.approx(
        [1.0, 0.8, 0.8]
    )
    assert isotonic_decreasing([]) == []


def test_isotonic_decreasing_rejects_bad_weights():
    with pytest.raises(ValueError):
        isotonic_decreasing([1.0, 0.0], [1.0, 0.0])


def test_frontier_interpolates_the_50_percent_bracket():
    score = estimate_from_counts(
        {
            1: (5, 5),
            2: (5, 5),
            3: (5, 5),
            4: (4, 5),
            5: (2, 5),
            6: (0, 5),
        },
        bootstrap_replicates=0,
    )
    assert score.score == pytest.approx(4.75)
    assert score.size == pytest.approx(ideal_size_for_level(4.75))
    assert score.censored is None
    assert score.ci is None
    assert score.levels[3]["p"] == pytest.approx(0.8)
    assert score.levels[4]["p"] == pytest.approx(0.4)


def test_extension_invariance():
    base = {
        1: (5, 5),
        2: (5, 5),
        3: (5, 5),
        4: (4, 5),
        5: (2, 5),
        6: (0, 5),
    }
    extended = dict(base)
    extended.update({7: (0, 5), 8: (0, 5), 9: (0, 5)})
    a = estimate_from_counts(base, bootstrap_replicates=0)
    b = estimate_from_counts(extended, bootstrap_replicates=0)
    assert a.score == pytest.approx(b.score)
    assert a.size == pytest.approx(b.size)


def test_all_pass_is_upper_censored():
    score = estimate_from_counts(
        {1: (5, 5), 2: (5, 5), 3: (5, 5)},
        bootstrap_replicates=0,
    )
    assert score.score is None
    assert score.size is None
    assert score.censored == "upper"
    assert score.bound == 3
    assert score.rank_key == float("inf")


def test_all_fail_is_lower_censored():
    score = estimate_from_counts(
        {1: (0, 5), 2: (0, 5)},
        bootstrap_replicates=0,
    )
    assert score.score is None
    assert score.censored == "lower"
    assert score.bound == 1
    assert score.rank_key == float("-inf")


def test_exact_half_at_the_last_level_is_finite():
    score = estimate_from_counts(
        {1: (5, 5), 2: (5, 10)},
        bootstrap_replicates=0,
    )
    assert score.score == pytest.approx(2.0)
    assert score.censored == "upper"
    assert score.is_finite


def test_flat_half_curve_is_ambiguous():
    score = estimate_from_counts(
        {1: (5, 10), 2: (5, 10), 3: (5, 10)},
        bootstrap_replicates=0,
    )
    assert score.score == pytest.approx(2.0)
    assert score.censored == "ambiguous"


def test_empty_levels_are_ignored():
    score = estimate_from_counts(
        {1: (5, 5), 2: (0, 0), 3: (0, 5)},
        bootstrap_replicates=0,
    )
    assert score.score == pytest.approx(2.0)


def test_non_monotonic_noise_is_smoothed():
    score = estimate_from_counts(
        {1: (5, 5), 2: (0, 5), 3: (5, 5), 4: (0, 5)},
        bootstrap_replicates=0,
    )
    assert score.censored is None
    assert score.score is not None
    assert 1.0 <= score.score <= 4.0
    assert score.levels[1]["smoothed"] == pytest.approx(0.5)


def test_bootstrap_interval_is_deterministic():
    counts = {
        1: (5, 5),
        2: (4, 5),
        3: (2, 5),
        4: (0, 5),
        5: (0, 5),
    }
    first = estimate_from_counts(counts, bootstrap_replicates=200, bootstrap_seed=7)
    second = estimate_from_counts(counts, bootstrap_replicates=200, bootstrap_seed=7)
    assert first.ci == second.ci
    assert first.size_ci == second.size_ci
    assert first.ci is not None
    assert first.ci[0] <= first.ci[1]
    assert first.size_ci is not None
    assert first.size_ci[0] <= first.size_ci[1]
    assert first.score is not None
    assert first.size is not None


def test_estimate_from_outcomes():
    score = estimate_from_outcomes(
        {
            1: [True, True, True, True, True],
            2: [True, True, True, False, False],
            3: [True, True, False, False, False],
            4: [False, False, False, False, False],
        },
        bootstrap_replicates=0,
    )
    assert score.score == pytest.approx(2.5)


def test_requires_at_least_one_valid_level():
    with pytest.raises(ValueError):
        estimate_frontier([], bootstrap_replicates=0)
    with pytest.raises(ValueError):
        estimate_from_counts({}, bootstrap_replicates=0)


def test_level_result_validation():
    with pytest.raises(ValueError):
        LevelResult.from_counts(0, 1, 1)
    with pytest.raises(ValueError):
        LevelResult.from_counts(1, 2, 1)
    with pytest.raises(ValueError):
        LevelResult.from_counts(1, -1, 1)
    result = LevelResult.from_outcomes(3, [True, False, True])
    assert result.valid == 3
    assert result.correct == 2
    assert result.p == pytest.approx(2 / 3)


def test_score_payload_is_json_serializable():
    score = estimate_from_counts(
        {1: (5, 5), 2: (0, 5)},
        bootstrap_replicates=0,
    )
    payload = score.to_dict()
    encoded = json.dumps(payload)
    assert "score" in json.loads(encoded)


def test_final_half_plateau_is_ambiguous_not_upper_censored():
    # 2/5 then 3/5 at the last two levels: isotonic pools them to a 0.5
    # plateau. The frontier is inside the plateau, not at the final level.
    score = estimate_from_counts(
        {
            1: (5, 5),
            2: (5, 5),
            3: (5, 5),
            4: (5, 5),
            5: (2, 5),
            6: (3, 5),
        },
        bootstrap_replicates=0,
    )
    assert score.score == pytest.approx(5.5)
    assert score.censored == "ambiguous"
    assert score.bound == 6
    assert score.is_finite
