"""Core data types used across EquationBench."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

AnswerType = Literal["integer", "rational", "integer_list"]
ParseStatus = Literal[
    "correct",
    "wrong",
    "unparseable",
    "provider_error",
    "timeout",
    "refusal",
]


#: Failures of the provider, not answers from the model.  They are excluded from
#: the frontier denominator.
INFRA_STATUSES: tuple[ParseStatus, ...] = ("provider_error", "timeout")


Level = int | float


def normalize_level(value: float) -> Level:
    """A ladder level: a whole number, or a half level such as ``10.5``.

    Whole levels are always ``int``, because a level's text form is part of its
    task seed and ``"10.0"`` would generate different tasks from ``"10"``.
    """
    doubled = float(value) * 2
    if not doubled.is_integer():
        raise ValueError(f"levels must be whole or half steps, got {value}")
    return int(value) if float(value).is_integer() else float(value)


def canonical_json(value: Any) -> str:
    """Stable JSON encoding used for hashes and dataset serialization."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GenResult:
    """A generated task before it receives a deterministic task id."""

    prompt: str
    answer: str
    answer_type: AnswerType
    solution: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Task:
    task_id: str
    family: str
    level: Level
    seed: int
    prompt: str
    answer: str
    answer_type: AnswerType
    solution: str
    metadata: dict[str, Any]
    generator_version: str
    prompt_version: str

    def public_dict(self) -> dict[str, Any]:
        """Task representation safe to hand to a model."""
        return {
            "task_id": self.task_id,
            "family": self.family,
            "level": self.level,
            "prompt": self.prompt,
        }

    def to_dict(self, include_answer: bool = True, include_solution: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "task_id": self.task_id,
            "family": self.family,
            "level": self.level,
            "seed": self.seed,
            "prompt": self.prompt,
            "answer_type": self.answer_type,
            "metadata": self.metadata,
            "generator_version": self.generator_version,
            "prompt_version": self.prompt_version,
        }
        if include_answer:
            data["answer"] = self.answer
        if include_solution:
            data["solution"] = self.solution
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(
            task_id=data["task_id"],
            family=data["family"],
            level=normalize_level(data["level"]),
            seed=int(data["seed"]),
            prompt=data["prompt"],
            answer=data["answer"],
            answer_type=data["answer_type"],
            solution=data.get("solution", ""),
            metadata=data.get("metadata", {}),
            generator_version=data.get("generator_version", ""),
            prompt_version=data.get("prompt_version", ""),
        )


@dataclass
class Prediction:
    task_id: str
    model_key: str
    raw_response: str
    parsed_answer: str | None
    correct: bool
    parse_status: ParseStatus
    error: str | None = None
    latency_ms: int = 0
    usage: dict[str, Any] = field(default_factory=dict)
    cost_usd: float | None = None
    attempts: int = 1
    model_info: dict[str, Any] = field(default_factory=dict)
    stop_reason: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    @property
    def is_infra(self) -> bool:
        return self.parse_status in INFRA_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "model_key": self.model_key,
            "raw_response": self.raw_response,
            "parsed_answer": self.parsed_answer,
            "correct": self.correct,
            "parse_status": self.parse_status,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "usage": self.usage,
            "cost_usd": self.cost_usd,
            "attempts": self.attempts,
            "model_info": self.model_info,
            "stop_reason": self.stop_reason,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Prediction":
        return cls(
            task_id=data["task_id"],
            model_key=data["model_key"],
            raw_response=data.get("raw_response", ""),
            parsed_answer=data.get("parsed_answer"),
            correct=bool(data.get("correct", False)),
            parse_status=data.get("parse_status", "unparseable"),
            error=data.get("error"),
            latency_ms=int(data.get("latency_ms", 0)),
            usage=data.get("usage", {}),
            cost_usd=data.get("cost_usd"),
            attempts=int(data.get("attempts", 1)),
            model_info=data.get("model_info", {}),
            stop_reason=data.get("stop_reason"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
        )


@dataclass
class Completion:
    """Provider response, independent of the benchmark's answer parsing."""

    text: str
    usage: dict[str, Any] = field(default_factory=dict)
    cost_usd: float | None = None
    latency_ms: int = 0
    model_info: dict[str, Any] = field(default_factory=dict)
    stop_reason: str | None = None
    error: str | None = None
    error_kind: str | None = None
    attempts: int = 1
    raw_stdout: str | None = None
    raw_stderr: str | None = None


@dataclass(frozen=True)
class ModelSpec:
    key: str
    name: str
    lab: str
    provider: str
    model: str
    thinking: str = "max"
    provider_kind: str = "pi"
    base_url: str | None = None
    api_key_env: str | None = None
    enabled: bool = True
    division: str = "standard"
    color: str = "#a3e635"
    notes: str = ""
    price_input: float | None = None
    price_output: float | None = None
    max_output_tokens: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "lab": self.lab,
            "provider": self.provider,
            "model": self.model,
            "thinking": self.thinking,
            "provider_kind": self.provider_kind,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "enabled": self.enabled,
            "division": self.division,
            "color": self.color,
            "notes": self.notes,
            "price_input": self.price_input,
            "price_output": self.price_output,
            "max_output_tokens": self.max_output_tokens,
            "extra": self.extra,
        }
