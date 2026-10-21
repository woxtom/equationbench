"""Provider protocol shared by the pi CLI and direct API adapters."""

from __future__ import annotations

from typing import Protocol

from ..types import Completion, ModelSpec


class Provider(Protocol):
    spec: ModelSpec

    def complete(self, system: str, prompt: str, timeout: float | None) -> Completion:
        ...


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, kind: str = "provider_error") -> None:
        super().__init__(message)
        self.kind = kind
