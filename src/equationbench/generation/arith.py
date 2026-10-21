"""Deeply nested exact integer arithmetic."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Union

from ..prompts import wrap_task
from ..types import GenResult

LEVEL_SPECS = {
    1: {"ops": 6, "leaf_bound": 10, "max_exp": 3, "factorial": False, "pow_p": 0.0},
    2: {"ops": 14, "leaf_bound": 100, "max_exp": 3, "factorial": False, "pow_p": 0.0},
    3: {"ops": 26, "leaf_bound": 1_000, "max_exp": 4, "factorial": False, "pow_p": 0.10},
    4: {"ops": 48, "leaf_bound": 10_000, "max_exp": 4, "factorial": True, "pow_p": 0.14},
    5: {"ops": 90, "leaf_bound": 100_000, "max_exp": 5, "factorial": True, "pow_p": 0.18},
}

MAX_BITS = 16_000


@dataclass
class Leaf:
    value: int
    factorial: bool = False


@dataclass
class Op:
    op: str
    left: "Node"
    right: "Node"


@dataclass
class Pow:
    base: "Node"
    exponent: int


Node = Union[Leaf, Op, Pow]


def _make_leaf(rng: random.Random, bound: int, allow_factorial: bool) -> Leaf:
    if allow_factorial and rng.random() < 0.16:
        return Leaf(rng.randint(1, 12), factorial=True)
    return Leaf(rng.randint(1, bound))


def _format(node: Node) -> str:
    if isinstance(node, Leaf):
        return f"{node.value}!" if node.factorial else str(node.value)
    if isinstance(node, Op):
        return f"({_format(node.left)} {node.op} {_format(node.right)})"
    base = _format(node.base)
    if isinstance(node.base, (Op, Pow)) or (
        isinstance(node.base, Leaf) and (node.base.value < 0 or node.base.factorial)
    ):
        base = f"({base})"
    return f"{base}^{node.exponent}"


def _evaluate(node: Node) -> int:
    if isinstance(node, Leaf):
        return math.factorial(node.value) if node.factorial else node.value
    if isinstance(node, Op):
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if node.op == "+":
            return left + right
        if node.op == "-":
            return left - right
        if node.op == "*":
            return left * right
        raise ValueError(node.op)
    return _evaluate(node.base) ** node.exponent


def _depth(node: Node) -> int:
    if isinstance(node, Leaf):
        return 1
    if isinstance(node, Op):
        return 1 + max(_depth(node.left), _depth(node.right))
    return 1 + _depth(node.base)


def _collect_ops(node: Node, counts: dict[str, int]) -> None:
    if isinstance(node, Leaf):
        if node.factorial:
            counts["!"] += 1
        return
    if isinstance(node, Op):
        counts[node.op] += 1
        _collect_ops(node.left, counts)
        _collect_ops(node.right, counts)
        return
    counts["^"] += 1
    _collect_ops(node.base, counts)


def _wrap_expression(expression: str, width: int = 128) -> str:
    """Wrap a fully parenthesized expression at spaces for readability."""
    tokens = expression.split(" ")
    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = token if not current else current + " " + token
        if len(candidate) > width and current:
            lines.append(current)
            current = token
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines)


def _build_tree(rng: random.Random, level: int) -> Node:
    spec = LEVEL_SPECS[level]
    leaves: list[Leaf] = [_make_leaf(rng, spec["leaf_bound"], spec["factorial"])]
    root: Node = leaves[0]
    for _ in range(spec["ops"]):
        target = rng.choice(leaves)
        # Replace the target in-place by mutating a small wrapper would be awkward.
        # A tree walk replaces the first identical object; leaves are unique objects.
        new_right = _make_leaf(rng, spec["leaf_bound"], spec["factorial"])
        if rng.random() < spec["pow_p"]:
            exponent = rng.randint(2, spec["max_exp"])
            replacement: Node = Pow(target, exponent)
            new_leaf = None
        else:
            op = rng.choices(["+", "-", "*"], weights=[3, 3, 4], k=1)[0]
            replacement = Op(op, target, new_right)
            new_leaf = new_right
        root = _replace_leaf(root, target, replacement)
        if new_leaf is not None:
            leaves.append(new_leaf)
        if len(leaves) > spec["ops"] + 1:
            # A power node does not add a leaf, so this is only a safety cap.
            leaves = leaves[: spec["ops"] + 1]
    return root


def _replace_leaf(node: Node, target: Leaf, replacement: Node) -> Node:
    if node is target:
        return replacement
    if isinstance(node, Op):
        node.left = _replace_leaf(node.left, target, replacement)
        node.right = _replace_leaf(node.right, target, replacement)
        return node
    if isinstance(node, Pow):
        node.base = _replace_leaf(node.base, target, replacement)
        return node
    return node


def generate(level: int, rng: random.Random) -> GenResult:
    if level not in LEVEL_SPECS:
        raise ValueError(f"unknown arithmetic level: {level}")
    spec = LEVEL_SPECS[level]

    for _attempt in range(200):
        root = _build_tree(rng, level)
        answer = _evaluate(root)
        if answer.bit_length() <= MAX_BITS:
            break
    else:  # pragma: no cover - astronomically unlikely with these bounds
        raise RuntimeError("could not generate a bounded arithmetic expression")

    expression = _wrap_expression(_format(root))
    counts = {"+": 0, "-": 0, "*": 0, "^": 0, "!": 0}
    _collect_ops(root, counts)
    body = (
        "Evaluate the following integer expression exactly.\n\n"
        f"```\n{expression}\n```\n\n"
        "The operators have their usual meanings; `^` denotes exponentiation "
        "and `!` denotes factorial."
    )
    prompt = wrap_task(body, "integer")
    metadata = {
        "ops": spec["ops"],
        "leaf_bound": spec["leaf_bound"],
        "max_exp": spec["max_exp"],
        "factorial": spec["factorial"],
        "depth": _depth(root),
        "op_counts": counts,
        "answer_digits": len(str(abs(answer))),
        "prompt_chars": len(prompt),
    }
    return GenResult(
        prompt=prompt,
        answer=str(answer),
        answer_type="integer",
        solution=(
            f"Exact evaluation of the expression tree gives a {metadata['answer_digits']}-digit "
            f"integer."
        ),
        metadata=metadata,
    )
