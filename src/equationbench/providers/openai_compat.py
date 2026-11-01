"""Direct OpenAI-compatible Chat Completions adapter.

This is for local models and external users who do not use the pi CLI. It works
with vLLM, Ollama's OpenAI endpoint, LM Studio, OpenRouter, and similar servers.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from ..types import Completion, ModelSpec
from .base import ProviderError


class OpenAICompatProvider:
    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec
        if not spec.base_url:
            raise ProviderError(f"{spec.key}: base_url is required for openai-compatible providers")
        self.base_url = spec.base_url.rstrip("/")
        self.api_key = os.environ.get(spec.api_key_env or "OPENAI_API_KEY", "dummy")
        self.extra = dict(spec.extra or {})

    def complete(self, system: str, prompt: str, timeout: float | None) -> Completion:
        started = time.perf_counter()
        payload: dict[str, Any] = {
            "model": self.spec.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        if not self.extra.get("omit_temperature"):
            payload["temperature"] = self.extra.get("temperature", 0)
        if self.spec.max_output_tokens:
            payload["max_tokens"] = self.spec.max_output_tokens
        for key, value in self.extra.get("request", {}).items():
            payload[key] = value
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        headers.update(self.extra.get("headers", {}))
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException:
            return Completion(
                text="",
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=(
                    f"provider timed out after {timeout:.0f}s"
                    if timeout is not None
                    else "provider timed out"
                ),
                error_kind="timeout",
            )
        except httpx.HTTPError as exc:
            return Completion(
                text="",
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=str(exc),
                error_kind="provider_error",
            )
        latency = int((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            kind = "provider_error"
            if response.status_code == 429:
                kind = "rate_limit"
            elif response.status_code in (401, 403):
                kind = "auth"
            elif response.status_code == 402:
                kind = "billing"
            elif response.status_code >= 500:
                kind = "transient"
            return Completion(
                text="",
                latency_ms=latency,
                error=f"HTTP {response.status_code}: {response.text[:4000]}",
                error_kind=kind,
            )
        try:
            data = response.json()
        except ValueError:
            return Completion(
                text="",
                latency_ms=latency,
                error=f"invalid JSON response: {response.text[:2000]}",
                error_kind="provider_error",
            )
        choices = data.get("choices") or []
        if not choices:
            return Completion(
                text="",
                latency_ms=latency,
                error=f"no choices in response: {str(data)[:2000]}",
                error_kind="provider_error",
            )
        message = choices[0].get("message") or {}
        text = message.get("content") or ""
        if isinstance(text, list):
            text = "".join(
                block.get("text", "") for block in text if isinstance(block, dict)
            )
        usage = data.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens", 0) or 0)
        output_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens) or 0)
        normalized_usage = {
            "input": input_tokens,
            "output": output_tokens,
            "totalTokens": total_tokens,
        }
        reasoning_tokens = (
            (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
            if isinstance(usage.get("completion_tokens_details"), dict)
            else None
        )
        if reasoning_tokens is not None:
            normalized_usage["reasoning"] = int(reasoning_tokens)
        # OpenRouter reports the actual charge in usage.cost. Prefer it over a
        # local price estimate, because routers apply their own markups.
        reported_cost = usage.get("cost")
        cost = None
        if isinstance(reported_cost, (int, float)):
            cost = float(reported_cost)
        elif self.spec.price_input is not None or self.spec.price_output is not None:
            cost = (
                input_tokens / 1_000_000 * (self.spec.price_input or 0)
                + output_tokens / 1_000_000 * (self.spec.price_output or 0)
            )
        return Completion(
            text=text,
            usage=normalized_usage,
            cost_usd=cost,
            latency_ms=latency,
            model_info={
                "provider": self.spec.provider,
                "model": data.get("model", self.spec.model),
                "api": "openai-completions",
            },
            stop_reason=choices[0].get("finish_reason"),
            error=None if text.strip() else "provider returned an empty assistant message",
            error_kind=None if text.strip() else "empty",
        )
