"""Provider selection and model registry loading."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Iterable

from ..types import ModelSpec
from .base import Provider, ProviderError
from .openai_compat import OpenAICompatProvider
from .pi_cli import PiCliProvider

__all__ = [
    "Provider",
    "ProviderError",
    "PiCliProvider",
    "OpenAICompatProvider",
    "make_provider",
    "load_models",
    "models_by_key",
]


def make_provider(spec: ModelSpec) -> Provider:
    if spec.provider_kind in ("pi", "pi-cli"):
        return PiCliProvider(spec)
    if spec.provider_kind in ("openai", "openai-compatible", "openai_compat"):
        return OpenAICompatProvider(spec)
    raise ProviderError(f"unknown provider kind: {spec.provider_kind}")


def _model_from_dict(data: dict) -> ModelSpec:
    known = {
        "key",
        "name",
        "lab",
        "provider",
        "model",
        "thinking",
        "provider_kind",
        "base_url",
        "api_key_env",
        "enabled",
        "division",
        "color",
        "notes",
        "price_input",
        "price_output",
        "max_output_tokens",
    }
    extra = {key: value for key, value in data.items() if key not in known}
    return ModelSpec(**{key: data[key] for key in known if key in data}, extra=extra)


def load_models(path: Path | str) -> list[ModelSpec]:
    path = Path(path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    models = [_model_from_dict(row) for row in data.get("models", [])]
    keys = [model.key for model in models]
    if len(keys) != len(set(keys)):
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        raise ValueError(f"duplicate model keys in {path}: {duplicates}")
    return models


def models_by_key(models: Iterable[ModelSpec]) -> dict[str, ModelSpec]:
    return {model.key: model for model in models}
