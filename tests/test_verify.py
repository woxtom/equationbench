from __future__ import annotations

import pytest

from equationbench.verify import (
    canonicalize_answer,
    extract_answer_text,
    grade_response,
)


@pytest.mark.parametrize(
    "raw,answer_type,expected",
    [
        ('{"answer": "123"}', "integer", "123"),
        ("```json\n{\"answer\": 123}\n```", "integer", "123"),
        ("The answer is 1,234.", "integer", "1234"),
        ("\\boxed{123}", "integer", "123"),
        ("2^10", "integer", "1024"),
        ("2**10", "integer", "1024"),
        ("16/2", "integer", "8"),
        ("123.0", "integer", "123"),
        ('{"answer": "17/24"}', "rational", "17/24"),
        ("\\frac{17}{24}", "rational", "17/24"),
        ("17/24", "rational", "17/24"),
        ("0.5", "rational", "1/2"),
        ("2 3/4", "rational", "11/4"),
        ('{"answer": [3, -1, 7]}', "integer_list", "[3, -1, 7]"),
        ("[3, -1, 7]", "integer_list", "[3, -1, 7]"),
        ("(3, -1, 7)", "integer_list", "[3, -1, 7]"),
        ("x1 = 3, x2 = -1, x3 = 7", "integer_list", "[3, -1, 7]"),
        ('{"x1": 3, "x2": -1, "x3": 7}', "integer_list", "[3, -1, 7]"),
        ("3, -1, 7", "integer_list", "[3, -1, 7]"),
        ("**Final answer:** 42", "integer", "42"),
        ("The answer is $\\frac{3}{4}$.", "rational", "3/4"),
    ],
)
def test_parser_accepts_common_formats(raw, answer_type, expected):
    result = grade_response(raw, expected, answer_type)
    assert result.correct, result
    assert result.parsed_answer == expected
    assert extract_answer_text(raw) is not None


@pytest.mark.parametrize(
    "raw,answer_type,expected",
    [
        ("124", "integer", "123"),
        ("[3, -1]", "integer_list", "[3, -1, 7]"),
        ("1/3", "rational", "17/24"),
        ("I cannot solve this", "integer", "1"),
        ('{"answer": "0.333"}', "rational", "1/3"),
    ],
)
def test_parser_rejects_wrong_or_approximate_answers(raw, answer_type, expected):
    result = grade_response(raw, expected, answer_type)
    assert not result.correct


def test_canonicalize_expected_list():
    assert canonicalize_answer("[3, -1, 7]", "integer_list") == "[3, -1, 7]"
