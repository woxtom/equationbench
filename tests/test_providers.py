from __future__ import annotations

import json

import httpx
import pytest

from equationbench.providers import make_provider
from equationbench.providers.openai_compat import OpenAICompatProvider
from equationbench.providers.pi_cli import PiCliProvider
from equationbench.types import ModelSpec

COMPAT_SPEC = ModelSpec(
    key="local",
    name="Local",
    lab="Test",
    provider="local",
    model="m",
    provider_kind="openai-compatible",
    base_url="http://test/v1/",
    price_input=1.0,
    price_output=2.0,
)


@pytest.fixture
def compat(monkeypatch):
    """Answer the adapter's HTTP call with a handler instead of the network."""
    real_client = httpx.Client

    def install(handler) -> OpenAICompatProvider:
        monkeypatch.setattr(
            httpx,
            "Client",
            lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
        )
        return OpenAICompatProvider(COMPAT_SPEC)

    return install


def _ok(content='{"answer": [1]}', **usage) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "served",
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 500_000, **usage},
        },
    )


def test_compat_sends_prompt_and_normalizes_usage(compat):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return _ok(completion_tokens_details={"reasoning_tokens": 7})

    completion = compat(handler).complete("sys", "prompt", 5.0)
    assert seen["url"] == "http://test/v1/chat/completions"
    assert [m["content"] for m in seen["body"]["messages"]] == ["sys", "prompt"]
    assert completion.error is None
    assert completion.usage["reasoning"] == 7
    assert completion.usage["totalTokens"] == 1_500_000
    assert completion.cost_usd == pytest.approx(2.0)
    assert completion.model_info["model"] == "served"


def test_compat_prefers_the_reported_cost(compat):
    completion = compat(lambda request: _ok(cost=0.25)).complete("s", "p", 5.0)
    assert completion.cost_usd == pytest.approx(0.25)


@pytest.mark.parametrize(
    ("status", "kind"),
    [(429, "rate_limit"), (401, "auth"), (403, "auth"), (402, "billing"), (503, "transient"), (400, "provider_error")],
)
def test_compat_classifies_http_errors(compat, status, kind):
    completion = compat(lambda request: httpx.Response(status, text="nope")).complete("s", "p", 5.0)
    assert completion.error_kind == kind
    assert str(status) in completion.error


def test_compat_reports_timeouts(compat):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    completion = compat(handler).complete("s", "p", 5.0)
    assert completion.error_kind == "timeout"


@pytest.mark.parametrize(
    ("response", "kind"),
    [
        (httpx.Response(200, text="not json"), "provider_error"),
        (httpx.Response(200, json={"choices": []}), "provider_error"),
        (_ok(content=""), "empty"),
    ],
)
def test_compat_flags_unusable_bodies(compat, response, kind):
    completion = compat(lambda request: response).complete("s", "p", 5.0)
    assert completion.error_kind == kind


def test_make_provider_selects_the_compat_adapter():
    assert isinstance(make_provider(COMPAT_SPEC), OpenAICompatProvider)


def test_pi_auth_error_message_is_classified():
    event = {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "content": [],
            "usage": {},
            "stopReason": "error",
            "errorMessage": '401: {"type":"authentication_error","code":"api_key_expired"}',
            "provider": "opencode-go",
            "model": "test",
        },
    }
    parsed = PiCliProvider._parse_stdout(json.dumps(event))
    assert parsed["error_kind"] == "auth"
    assert "api_key_expired" in parsed["error"]


def test_pi_successful_message():
    event = {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": '{"answer": "42"}'}],
            "usage": {"input": 10, "output": 4, "totalTokens": 14, "cost": {"total": 0.001}},
            "stopReason": "stop",
            "provider": "test",
            "model": "test",
        },
    }
    parsed = PiCliProvider._parse_stdout(json.dumps(event))
    assert parsed["text"] == '{"answer": "42"}'
    assert parsed["error"] is None
    assert parsed["cost_usd"] == 0.001


def test_pi_usage_limit_is_fatal_billing_error():
    event = {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "content": [],
            "usage": {},
            "stopReason": "error",
            "errorMessage": '429 {"type":"error","error":{"type":"GoUsageLimitError","message":"Go usage limit exceeded"}}',
        },
    }
    parsed = PiCliProvider._parse_stdout(json.dumps(event))
    assert parsed["error_kind"] == "billing"
    assert "usage limit" in parsed["error"].lower()
