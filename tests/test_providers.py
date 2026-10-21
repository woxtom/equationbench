from __future__ import annotations

import json

from equationbench.providers.pi_cli import PiCliProvider


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
