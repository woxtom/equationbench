from __future__ import annotations

import json
import random

import pytest

from equationbench.ladder_run import build_ladder_bundle
from equationbench.types import Completion, ModelSpec


@pytest.fixture(scope="session")
def tiny_dataset():
    return build_ladder_bundle([1, 2, 3, 4, 5], tasks_per_level=1)


class FakeProvider:
    """Deterministic fake model: correct with probability controlled by accuracy."""

    def __init__(self, spec: ModelSpec, accuracy: float = 1.0) -> None:
        self.spec = spec
        self.accuracy = accuracy
        self.rng = random.Random(hash(spec.key) & 0xFFFFFFFF)
        self.calls = 0

    def complete(self, system: str, prompt: str, timeout: float) -> Completion:
        self.calls += 1
        # The fake provider is given the task through a registry set by the test.
        task = getattr(self, "task_by_prompt")[prompt]
        if self.rng.random() < self.accuracy:
            answer = task.answer
        elif task.answer_type == "integer":
            answer = "0"
        elif task.answer_type == "rational":
            answer = "0"
        else:
            answer = "[0]"
        text = f"Fake reasoning.\n\n{json.dumps({'answer': answer})}"
        return Completion(
            text=text,
            usage={
                "input": 100,
                "output": 25,
                "totalTokens": 125,
                "cost": {"total": 0.001},
            },
            cost_usd=0.001,
            latency_ms=1000,
            model_info={"provider": "fake", "model": self.spec.model, "thinkingLevel": "off"},
            stop_reason="stop",
        )


@pytest.fixture
def fake_provider_factory(tiny_dataset):
    task_by_prompt = {task.prompt: task for task in tiny_dataset.tasks}

    def make(spec: ModelSpec, accuracy: float = 1.0) -> FakeProvider:
        provider = FakeProvider(spec, accuracy)
        provider.task_by_prompt = task_by_prompt
        return provider

    return make
