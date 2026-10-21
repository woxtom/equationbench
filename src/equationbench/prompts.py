"""Prompt construction for EquationBench.

The same wrapper is used for every model. Only the task body and the answer
shape change. Keeping prompt construction in one place makes prompt changes
explicit and versioned.
"""

from __future__ import annotations

from .types import AnswerType

SYSTEM_PROMPT = """\
You are solving EquationBench, a closed-book benchmark of exactly verifiable
mathematical problems. Tools, code execution, and external resources are not
available. Work exactly: do not round, approximate, or guess.

Your response may contain reasoning. It must end with a single JSON object
containing the final answer. Do not put anything after that JSON object. The
answer must be exact; the benchmark parses and compares it symbolically or as
an exact integer/rational."""

_ANSWER_FORMAT = {
    "integer": '{"answer": "123"} (the value must be an exact integer)',
    "rational": (
        '{"answer": "17/24"} (the value must be an exact reduced rational; '
        'integers are allowed when the denominator is 1)'
    ),
    "integer_list": (
        '{"answer": [3, -1, 7]} (exact integers in the requested order)'
    ),
}

_ANSWER_REQUIREMENT = {
    "integer": "Give one exact integer.",
    "rational": "Give one exact rational number in reduced form p/q (or an integer).",
    "integer_list": "Give the complete list of exact integers in the requested order.",
}


def wrap_task(body: str, answer_type: AnswerType) -> str:
    """Wrap a task body with the standard answer contract."""
    return (
        f"{body.strip()}\n\n"
        "Rules:\n"
        f"- {_ANSWER_REQUIREMENT[answer_type]}\n"
        "- Do not use decimal approximations unless the value is exactly an integer.\n"
        "- Your final line must contain exactly one JSON object with this shape: "
        f"{_ANSWER_FORMAT[answer_type]}.\n"
        "- The JSON object must be the last thing in your response."
    )


def prompt_fingerprint() -> str:
    """Hash-relevant representation of the prompt contract."""
    return SYSTEM_PROMPT + "\n" + "\n".join(
        f"{key}:{_ANSWER_FORMAT[key]}:{_ANSWER_REQUIREMENT[key]}"
        for key in sorted(_ANSWER_FORMAT)
    )
