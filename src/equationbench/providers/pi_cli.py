"""Run models through the ``pi`` CLI.

Using pi as the transport gives EquationBench one uniform, authenticated path to
many providers (OpenAI-compatible endpoints, Anthropic, Google, and gateways),
while ``--mode json`` supplies token usage and cost metadata for the leaderboard.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from ..types import Completion, ModelSpec


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif isinstance(block.get("text"), str):
                    parts.append(block["text"])
        return "".join(parts)
    if isinstance(content, dict):
        return _content_text(content.get("text", ""))
    return ""


def _classify_error(text: str) -> str:
    lowered = text.lower()
    if (
        "gousagelimiterror" in lowered
        or "usage limit exceeded" in lowered
        or "insufficient_balance" in lowered
        or "402 payment required" in lowered
    ):
        return "billing"
    if "429" in lowered or "rate limit" in lowered or "too many requests" in lowered:
        return "rate_limit"
    if "401" in lowered or "403" in lowered or "unauthorized" in lowered or "forbidden" in lowered:
        return "auth"
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    if "overloaded" in lowered or "503" in lowered or "502" in lowered or "500" in lowered:
        return "transient"
    if "not found" in lowered or "unknown model" in lowered or "unsupported model" in lowered:
        return "bad_model"
    return "provider_error"


class PiCliProvider:
    def __init__(
        self,
        spec: ModelSpec,
        *,
        executable: str | None = None,
        offline: bool = True,
        workdir: Path | None = None,
    ) -> None:
        self.spec = spec
        self.executable = executable or os.environ.get("EQB_PI_BIN") or shutil.which("pi") or "pi"
        self.offline = offline
        self._owned_workdir = workdir is None
        self.workdir = workdir or Path(tempfile.mkdtemp(prefix="eqb-pi-"))

    def __del__(self) -> None:  # pragma: no cover - best effort cleanup
        if self._owned_workdir:
            shutil.rmtree(self.workdir, ignore_errors=True)

    def _command(self, system: str, prompt: str, *, include_thinking: bool) -> list[str]:
        command = [
            self.executable,
            "-p",
            "--mode",
            "json",
            "--provider",
            self.spec.provider,
            "--model",
            self.spec.model,
            "--no-tools",
            "--no-session",
            "--no-context-files",
            "--no-extensions",
            "--no-skills",
            "--no-prompt-templates",
            "--no-mcp",
            "--system-prompt",
            system,
        ]
        if self.offline:
            command.append("--offline")
        if include_thinking and self.spec.thinking:
            command.extend(["--thinking", self.spec.thinking])
        command.append(prompt)
        return command

    def complete(self, system: str, prompt: str, timeout: float | None) -> Completion:
        started = time.perf_counter()
        include_thinking = True
        last_error: Completion | None = None
        for attempt in range(2):
            command = self._command(system, prompt, include_thinking=include_thinking)
            try:
                process = subprocess.run(
                    command,
                    cwd=self.workdir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=os.environ.copy(),
                )
            except subprocess.TimeoutExpired as exc:
                elapsed = int((time.perf_counter() - started) * 1000)
                message = (
                    f"provider timed out after {timeout:.0f}s"
                    if timeout is not None
                    else "provider timed out"
                )
                return Completion(
                    text="",
                    latency_ms=elapsed,
                    error=message,
                    error_kind="timeout",
                    attempts=attempt + 1,
                    raw_stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                    raw_stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
                )
            except OSError as exc:
                elapsed = int((time.perf_counter() - started) * 1000)
                return Completion(
                    text="",
                    latency_ms=elapsed,
                    error=str(exc),
                    error_kind="provider_error",
                    attempts=attempt + 1,
                )

            elapsed = int((time.perf_counter() - started) * 1000)
            combined = (process.stdout or "") + "\n" + (process.stderr or "")
            if process.returncode != 0:
                kind = _classify_error(combined)
                last_error = Completion(
                    text="",
                    latency_ms=elapsed,
                    error=combined.strip()[-4000:] or f"pi exited with {process.returncode}",
                    error_kind=kind,
                    attempts=attempt + 1,
                    raw_stdout=process.stdout,
                    raw_stderr=process.stderr,
                )
                # Some providers have no "off" thinking level. Retry once without
                # the flag rather than failing the task.
                if (
                    attempt == 0
                    and include_thinking
                    and self.spec.thinking
                    and "thinking" in combined.lower()
                    and ("support" in combined.lower() or "invalid" in combined.lower())
                ):
                    include_thinking = False
                    continue
                return last_error

            parsed = self._parse_stdout(process.stdout or "")
            if parsed.get("error"):
                last_error = Completion(
                    text=parsed.get("text", ""),
                    usage=parsed.get("usage", {}),
                    cost_usd=parsed.get("cost_usd"),
                    latency_ms=elapsed,
                    model_info=parsed.get("model_info", {}),
                    stop_reason=parsed.get("stop_reason"),
                    error=str(parsed["error"])[-4000:],
                    error_kind=parsed.get("error_kind", "provider_error"),
                    attempts=attempt + 1,
                    raw_stdout=process.stdout,
                    raw_stderr=process.stderr,
                )
                if parsed.get("error_kind") in ("billing", "auth", "bad_model"):
                    return last_error
                if attempt == 0:
                    continue
                return last_error

            text = parsed.get("text", "")
            if not text.strip():
                last_error = Completion(
                    text="",
                    usage=parsed.get("usage", {}),
                    latency_ms=elapsed,
                    model_info=parsed.get("model_info", {}),
                    stop_reason=parsed.get("stop_reason"),
                    error="provider returned an empty assistant message",
                    error_kind="empty",
                    attempts=attempt + 1,
                    raw_stdout=process.stdout,
                    raw_stderr=process.stderr,
                )
                if attempt == 0:
                    continue
                return last_error
            return Completion(
                text=text,
                usage=parsed.get("usage", {}),
                cost_usd=parsed.get("cost_usd"),
                latency_ms=elapsed,
                model_info=parsed.get("model_info", {}),
                stop_reason=parsed.get("stop_reason"),
                attempts=attempt + 1,
                raw_stdout=process.stdout,
                raw_stderr=process.stderr,
            )
        return last_error or Completion(
            text="", latency_ms=int((time.perf_counter() - started) * 1000), error="unknown provider failure"
        )

    @staticmethod
    def _parse_stdout(stdout: str) -> dict[str, Any]:
        assistant_messages: list[dict[str, Any]] = []
        errors: list[str] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_type = event.get("type")
            if event_type == "message_end":
                message = event.get("message", {})
                if message.get("role") == "assistant":
                    assistant_messages.append(message)
            elif event_type == "agent_end":
                for message in event.get("messages", []):
                    if message.get("role") == "assistant":
                        assistant_messages.append(message)
            elif event_type == "error":
                errors.append(str(event.get("error") or event))
        if assistant_messages:
            message = assistant_messages[-1]
            usage = message.get("usage") or {}
            cost = usage.get("cost") if isinstance(usage.get("cost"), dict) else {}
            cost_total = cost.get("total") if isinstance(cost, dict) else None
            stop_reason = message.get("stopReason")
            error_message = message.get("errorMessage")
            error_text = None
            if error_message:
                error_text = str(error_message)
            elif stop_reason in ("error", "aborted"):
                error_text = f"stop reason: {stop_reason}"
            return {
                "text": _content_text(message.get("content", "")),
                "usage": usage,
                "cost_usd": cost_total,
                "model_info": {
                    "provider": message.get("provider"),
                    "model": message.get("model"),
                    "api": message.get("api"),
                    "thinkingLevel": message.get("thinkingLevel"),
                    "responseId": message.get("responseId"),
                },
                "stop_reason": stop_reason,
                "error": error_text,
                "error_kind": _classify_error(error_text) if error_text else None,
            }
        if errors:
            text = "\n".join(errors)
            return {"error": text, "error_kind": _classify_error(text)}
        return {
            "error": "pi produced no assistant message",
            "error_kind": "provider_error",
        }
