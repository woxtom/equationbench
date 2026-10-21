"""Answer extraction, canonicalization, and exact grading.

Models are asked for JSON, but real models are messy. The parser is deliberately
generous about presentation and strict about mathematics: it accepts JSON,
boxed answers, LaTeX fractions, equivalent arithmetic expressions, and labeled
solution lists, then canonicalizes them before exact comparison.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from .mathutil import format_integer_list, format_rational
from .types import AnswerType, ParseStatus


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class GradeResult:
    correct: bool
    parsed_answer: str | None
    status: ParseStatus
    error: str | None = None


def _strip_outer(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json|text|latex)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    # A common pattern is a quoted scalar with a trailing period.
    text = text.strip().strip("`").strip()
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    # Sentence punctuation after a displayed result is not part of the value.
    text = re.sub(r"[.;,]\s*$", "", text).strip()
    return text


def extract_answer_text(raw: str) -> str | None:
    """Return the most plausible final-answer payload from a response."""
    if not raw or not raw.strip():
        return None
    text = raw

    # 1. The last JSON object containing an "answer" key. Use raw_decode so
    # nested arrays/objects (e.g. a list of integers) are handled correctly.
    decoder = json.JSONDecoder()
    candidates: list[Any] = []
    for match in re.finditer(r"\{", text):
        start = match.start()
        try:
            obj, _end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and any(
            key.lower() in {"answer", "final_answer", "final answer"} for key in obj
        ):
            candidates.append(obj)
    if candidates:
        obj = candidates[-1]
        for key, value in obj.items():
            if key.lower() in {"answer", "final_answer", "final answer"}:
                if isinstance(value, (dict, list)):
                    return json.dumps(value, ensure_ascii=False)
                return str(value)

    # 2. A fenced block that contains JSON or a bare answer.
    fences = re.findall(r"```(?:json|text|latex)?\s*(.*?)```", text, flags=re.DOTALL)
    if fences:
        candidate = _strip_outer(fences[-1])
        if candidate:
            return candidate

    # 3. Boxed answer, with brace matching.
    boxed = _find_last_boxed(text)
    if boxed is not None:
        return boxed

    # 4. Explicit answer labels on the last line. Normalize markdown-bolded
    # labels such as "**Final answer:** 42" first.
    label_text = re.sub(
        r"\*\*\s*(final\s+answer|answer)\s*:?\s*\*\*",
        r"\1:",
        text,
        flags=re.IGNORECASE,
    )
    label_patterns = [
        r"(?im)^\s*(?:final\s+answer|answer)\s*(?:is|:)\s*(.+?)\s*$",
        r"(?i)\b(?:final\s+answer|answer)\s*(?:is|:)\s*(.+?)\s*$",
    ]
    for pattern in label_patterns:
        matches = re.findall(pattern, label_text)
        if matches:
            return _strip_outer(matches[-1])

    # 5. A JSON-like object with an unquoted answer (handled after JSON).
    match = re.search(
        r'"answer"\s*:\s*([^\n]+?)\s*\}?\s*$', text, flags=re.IGNORECASE
    )
    if match:
        return _strip_outer(match.group(1))

    # 6. Last non-empty line, stripped of markdown.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    last = lines[-1]
    last = re.sub(r"^\s*[-*]\s*", "", last)
    # Strip a markdown-bolded label or whole-line emphasis, but never remove
    # multiplication signs from a mathematical expression.
    last = re.sub(r"^\*\*[^*]+\*\*\s*", "", last)
    last = re.sub(r"^\*\*(.*?)\*\*$", r"\1", last)
    last = re.sub(r"^\*(.*?)\*$", r"\1", last)
    last = re.sub(r"^__(.*?)__$", r"\1", last)
    return _strip_outer(last)


def _find_last_boxed(text: str) -> str | None:
    marker = "\\boxed{"
    idx = text.rfind(marker)
    if idx == -1:
        return None
    start = idx + len(marker)
    depth = 1
    i = start
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    if depth != 0:
        return None
    return text[start : i - 1].strip()


def _normalize_latex(text: str) -> str:
    text = text.strip()
    text = text.replace("−", "-").replace("–", "-").replace("×", "*").replace("÷", "/")
    text = text.replace("\\left", "").replace("\\right", "")
    text = text.replace("\\,", "").replace("\\!", "").replace("\\;", "")
    text = text.replace("\\cdot", "*").replace("\\times", "*").replace("\\div", "/")
    text = re.sub(r"\\text\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", text)
    # Resolve simple nested \frac{a}{b} expressions.
    for _ in range(4):
        new = re.sub(
            r"\\(?:d|t)?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}",
            r"((\1)/(\2))",
            text,
        )
        if new == text:
            break
        text = new
    text = text.replace("$", "")
    text = re.sub(r"\^\s*\{([^{}]*)\}", r"^(\1)", text)
    return text.strip()


def _safe_fraction(expression: str) -> Fraction:
    """Evaluate + - * / ** on exact integers, with no names or calls."""
    expression = _normalize_latex(expression)
    expression = expression.strip()
    if not expression:
        raise ParseError("empty expression")
    if len(expression) > 5000:
        raise ParseError("answer expression is too long")
    # A caret is exponentiation in the model's notation, not Python XOR.
    expression = expression.replace("^", "**")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ParseError(f"not an arithmetic expression: {expression[:80]}") from exc

    node_count = 0

    def evaluate(node: ast.AST) -> Fraction:
        nonlocal node_count
        node_count += 1
        if node_count > 2000:
            raise ParseError("answer expression is too complex")
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                raise ParseError("boolean is not a number")
            if isinstance(node.value, int):
                return Fraction(node.value)
            if isinstance(node.value, float):
                # Exact decimal conversion, but reject non-finite values.
                return Fraction(str(node.value))
            raise ParseError("non-numeric constant")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left = evaluate(node.left)
            right = evaluate(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ParseError("division by zero")
                return left / right
            if isinstance(node.op, ast.Pow):
                if right.denominator != 1:
                    raise ParseError("non-integer exponent")
                exponent = int(right)
                if abs(exponent) > 100_000:
                    raise ParseError("exponent is too large")
                if exponent < 0 and left == 0:
                    raise ParseError("division by zero")
                return left**exponent
        raise ParseError("unsupported syntax in answer expression")

    try:
        result = evaluate(tree)
    except (OverflowError, ValueError) as exc:
        raise ParseError("could not evaluate answer expression") from exc
    return result


def _parse_integer_text(text: str) -> int:
    text = _strip_outer(text)
    text = _normalize_latex(text)
    if "=" in text:
        # Take the right-hand side of the final equals sign.
        text = text.rsplit("=", 1)[1].strip()
    text = text.strip().strip("'\"")
    text = re.sub(r"[\s,_]", "", text)
    if re.fullmatch(r"[+-]?\d+", text):
        return int(text)
    value = _safe_fraction(_strip_outer(text))
    if value.denominator != 1:
        raise ParseError(f"expected an integer, got {value}")
    return value.numerator


def _parse_rational_text(text: str) -> Fraction:
    text = _strip_outer(text)
    text = _normalize_latex(text)
    if "=" in text:
        text = text.rsplit("=", 1)[1].strip()
    text = text.strip().strip("'\"")
    # Accept a mixed number such as 2 3/4 before removing whitespace.
    mixed = re.fullmatch(r"([+-]?\d+)\s+(\d+)/(\d+)", text)
    if mixed:
        whole = int(mixed.group(1))
        sign = -1 if whole < 0 else 1
        return Fraction(whole) + sign * Fraction(int(mixed.group(2)), int(mixed.group(3)))
    text = re.sub(r"\s*([/])\s*", r"\1", text)
    text = re.sub(r"[\s,]", "", text)
    if re.fullmatch(r"[+-]?\d+", text):
        return Fraction(int(text))
    if re.fullmatch(r"[+-]?\d+/\d+", text):
        return Fraction(text)
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\.\d+)", text):
        return Fraction(text)
    return _safe_fraction(_strip_outer(text))


def _parse_integer_list_text(text: str) -> list[int]:
    text = _strip_outer(text)
    # Prefer a JSON array anywhere in the payload.
    arrays = re.findall(r"\[[^\[\]]*\]", text, flags=re.DOTALL)
    for candidate in reversed(arrays):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list) and all(
            isinstance(x, (int, float, str)) and not isinstance(x, bool) for x in data
        ):
            return [int(_parse_integer_text(str(x))) for x in data]
    # A tuple, perhaps with LaTeX commas.
    tuples = re.findall(r"\([^()]*\)", text, flags=re.DOTALL)
    for candidate in reversed(tuples):
        inner = candidate[1:-1].strip()
        if not inner:
            continue
        pieces = [p for p in re.split(r"[,;]", inner) if p.strip()]
        if len(pieces) >= 1:
            try:
                return [_parse_integer_text(p) for p in pieces]
            except ParseError:
                continue
    # Labeled values: x1 = 3, x2 = -1, ...
    labeled = re.findall(
        r"(?:x|a|y)_?\s*(\d+)\s*[=:]\s*([+-]?\d+)", text, flags=re.IGNORECASE
    )
    if labeled:
        ordered = sorted(((int(idx), int(value)) for idx, value in labeled), key=lambda p: p[0])
        return [value for _, value in ordered]
    # A JSON object keyed by variable name.
    for candidate in reversed(re.findall(r"\{[^{}]*\}", text, flags=re.DOTALL)):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            pairs = []
            for key, value in data.items():
                match = re.fullmatch(r"[A-Za-z]?_?(\d+)", str(key))
                if match:
                    pairs.append((int(match.group(1)), int(_parse_integer_text(str(value)))))
            if pairs:
                return [value for _, value in sorted(pairs)]
    # Comma-separated numbers in the final line.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        line = re.sub(r"^.*?(?:answer|solution)\s*[=:]\s*", "", line, flags=re.IGNORECASE)
        pieces = [p for p in re.split(r"[,;]", line) if p.strip()]
        if len(pieces) >= 2:
            try:
                return [_parse_integer_text(p) for p in pieces]
            except ParseError:
                pass
    # A single value is a valid one-element list only if it is clearly a list.
    raise ParseError("could not find a complete list of integers")


def canonicalize_answer(raw: str, answer_type: AnswerType) -> str:
    if not raw or not raw.strip():
        raise ParseError("empty answer")
    if answer_type == "integer":
        return str(_parse_integer_text(raw))
    if answer_type == "rational":
        return format_rational(_parse_rational_text(raw))
    if answer_type == "integer_list":
        return format_integer_list(_parse_integer_list_text(raw))
    raise ParseError(f"unsupported answer type: {answer_type}")


def grade_response(raw: str, expected: str, answer_type: AnswerType) -> GradeResult:
    extracted = extract_answer_text(raw)
    if extracted is None:
        return GradeResult(False, None, "unparseable", "no answer found")
    try:
        parsed = canonicalize_answer(extracted, answer_type)
    except ParseError as exc:
        return GradeResult(False, None, "unparseable", str(exc))
    try:
        expected_canonical = canonicalize_answer(expected, answer_type)
    except ParseError as exc:  # pragma: no cover - dataset integrity failure
        raise ValueError(f"dataset has an invalid expected answer: {expected!r}") from exc
    if parsed == expected_canonical:
        return GradeResult(True, parsed, "correct")
    return GradeResult(False, parsed, "wrong")
