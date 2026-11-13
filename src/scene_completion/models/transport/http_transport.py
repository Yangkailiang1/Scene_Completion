"""Credential-safe chat transport and environment references."""

from __future__ import annotations

import http.client
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class ValidationFailure(ValueError):
    pass


def load_ecnu_env_file(path: str | Path, extra_keys=()) -> list[str]:
    """Load documented and explicitly referenced model settings without logging credentials."""
    allowed = {
        "ECNU_MAX_MODEL",
        "ECNU_MAX_API_KEY",
        "ECNU_MAX_BASE_URL",
        "ECNU_EMBEDDING_TEXT",
        "ECNU_EMBEDDING_VL",
        "ECNU_RERANK",
        "ECNU_RERANK_VL",
    }
    allowed.update(
        {
            "SCENE_API_BASE_URL",
            "SCENE_API_KEY",
            "SCENE_AGENT_MODEL",
            "SCENE_EMBEDDING_MODEL",
            "SCENE_RERANK_MODEL",
            "SCENE_EMBEDDING_BASE_URL",
            "SCENE_EMBEDDING_API_KEY",
            "SCENE_REVIEW_MODEL",
            "SCENE_MAX_CONCURRENCY",
        }
    )
    allowed.update(
        key
        for key in extra_keys
        if isinstance(key, str)
        and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
        and key.upper() not in {"HOME", "CODEX_HOME", "PATH", "PYTHONPATH", "SHELL", "USERPROFILE"}
    )
    loaded = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("export "):
            text = text[7:].lstrip()
        if "=" not in text:
            continue
        key, value = text.split("=", 1)
        key, value = key.strip(), value.strip()
        if key not in allowed:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if not value:
            raise ValidationFailure(
                [f"ECNU env file has an empty {key} value at line {line_number}"]
            )
        os.environ.setdefault(key, value)
        loaded.append(key)
    return loaded


def _resolve_env_reference(value: Any) -> str:
    text = str(value or "").strip()
    match = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", text)
    return os.environ.get(match.group(1), "") if match else text


def _content_from_response(value: dict[str, Any]) -> str:
    try:
        content = value["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValidationFailure(
            ["semantic API response does not match OpenAI chat.completions format"]
        ) from exc
    if isinstance(content, list):
        content = "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    text = str(content).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    return text


def _retry_after_seconds(headers):
    """Missing Retry-After uses the caller's cooldown, never a synthetic one second."""
    raw = headers.get("Retry-After") if headers else None
    if raw is None:
        return None
    try:
        value = float(raw)
    except (ValueError, TypeError):
        from email.utils import parsedate_to_datetime

        try:
            value = parsedate_to_datetime(raw).timestamp() - time.time()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(1.0, min(300.0, value))


def _post_chat_completions_diagnostic(
    url: str,
    api_key: str,
    body: dict[str, Any],
    timeout: float,
    retries: int,
    *,
    idle_timeout=None,
    total_timeout=None,
    capture_reasoning=False,
    display_reasoning=False,
    throughput_policy=None,
) -> dict[str, Any]:
    from scene_completion.models.transport.provider_response import (
        InvalidProviderResponse,
        invalid_chat_response,
    )

    chat = url.rstrip("/").endswith("/chat/completions")
    request_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=request_body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    last_error = "request failed"
    diagnostic = None
    retry_delay = None
    from scene_completion.infrastructure.performance import _active_profiler

    observer = _active_profiler.get()
    for attempt in range(retries + 1):
        attempt_start = time.perf_counter()
        attempt_status = "failed"
        attempt_code = None
        transport_phase = "connect_or_headers"
        if observer:
            observer.emit("transport_attempt_start", "running", attempt=attempt + 1)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                attempt_code = getattr(response, "status", None)
                if body.get("stream") and "application/json" not in response.headers.get(
                    "Content-Type", ""
                ):
                    from scene_completion.models.transport.streaming import read_chat_stream

                    transport_phase = "stream_read"
                    idle = float(idle_timeout if idle_timeout is not None else timeout)
                    total = float(total_timeout if total_timeout is not None else timeout)
                    try:
                        set_read_timeout = response.fp.raw._sock.settimeout
                    except AttributeError:
                        set_read_timeout = None
                    value = read_chat_stream(
                        response,
                        attempt_start,
                        total,
                        observer,
                        idle_timeout=idle,
                        set_read_timeout=set_read_timeout,
                        capture_reasoning=capture_reasoning,
                        display_reasoning=display_reasoning,
                        throughput_policy=throughput_policy,
                        requested_model=body.get("model"),
                    )
                else:
                    transport_phase = "response_decode"
                    raw = response.read()
                    if chat and not raw.strip():
                        raise InvalidProviderResponse("empty_body")
                    value = json.loads(raw.decode("utf-8"))
                    if chat and (reason := invalid_chat_response(value)):
                        raise InvalidProviderResponse(
                            reason, usage=value.get("usage") if isinstance(value, dict) else None
                        )
                    if isinstance(value, dict):
                        value.pop("_scene_completion_metrics", None)
                    if isinstance(value, dict) and "choices" in value:
                        from scene_completion.models.transport.provider_reasoning import (
                            buffered_response,
                        )

                        value = buffered_response(
                            value, capture=capture_reasoning, display=display_reasoning
                        )
                if chat and body.get("stream") and (reason := invalid_chat_response(value)):
                    raise InvalidProviderResponse(
                        reason, usage=value.get("usage") if isinstance(value, dict) else None
                    )
                attempt_status = "complete"
                if isinstance(value, dict):
                    metrics = value.get("_scene_completion_metrics")
                    value["_scene_completion_metrics"] = {
                        **(metrics if isinstance(metrics, dict) else {}),
                        "transport_attempts": attempt + 1,
                    }
                return value
        except InvalidProviderResponse as exc:
            exc.response_diagnostic.update(phase=transport_phase, transport_attempts=attempt + 1)
            if type(attempt_code) is int:
                exc.response_diagnostic["http_status"] = attempt_code
            raise
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            if chat:
                raise InvalidProviderResponse(
                    "invalid_json",
                    phase=transport_phase,
                    http_status=attempt_code,
                    attempts=attempt + 1,
                ) from None
            if not isinstance(exc, json.JSONDecodeError):
                raise
            last_error = type(exc).__name__
            diagnostic = {"failure_category": "connection_failed", "phase": transport_phase}
        except urllib.error.HTTPError as exc:
            attempt_code = exc.code
            last_error = f"HTTP {exc.code}"
            # Inspect only for a classified limit; never persist or display an
            # untrusted server body, which may echo credentials or input text.
            try:
                error_body = exc.read(8192).decode("utf8", errors="replace").casefold()
            except OSError:
                error_body = ""
            exhausted = any(
                term in error_body
                for term in (
                    "insufficient_quota",
                    "quota_exhausted",
                    "credits",
                    "billing_limit",
                    "额度不足",
                    "余额不足",
                )
            )
            missing_model = exc.code == 400 and any(
                term in error_body
                for term in (
                    "model_not_found",
                    "model_not_supported",
                    "model not found",
                    "unsupported model",
                    "model is not available",
                    "模型不存在",
                    "模型不可用",
                )
            )
            diagnostic = {
                "http_status": exc.code,
                "failure_category": "quota_exhausted"
                if exhausted
                else (
                    "model_unavailable"
                    if missing_model
                    else {
                        401: "authentication_failed",
                        403: "access_denied",
                        404: "model_unavailable",
                        408: "transport_timeout",
                        504: "transport_timeout",
                        429: "rate_limited",
                    }.get(exc.code, "transport_error")
                ),
            }
            invalid_config = exc.code in (400, 422) and any(
                term in error_body
                for term in (
                    "invalid_parameter",
                    "invalid parameter",
                    "unsupported parameter",
                    "parameter is restricted",
                )
            )
            if invalid_config and not missing_model and not exhausted:
                diagnostic.update(
                    failure_category="invalid_configuration", configuration_required=True
                )
                parameter = next(
                    (
                        name
                        for name in (
                            "enable_thinking",
                            "thinking",
                            "reasoning_effort",
                            "reasoning_content",
                            "response_format",
                            "tool_choice",
                            "parallel_tool_calls",
                            "max_completion_tokens",
                            "max_tokens",
                            "thinking_budget",
                        )
                        if name in error_body
                    ),
                    None,
                )
                if parameter:
                    diagnostic["parameter"] = parameter
            if (
                chat
                and exc.code in (400, 413, 422)
                and any(
                    marker in error_body
                    for marker in (
                        "context_length_exceeded",
                        "context_window_exceeded",
                        "maximum context length",
                        "exceeds the context window",
                        "prompt is too long",
                    )
                )
            ):
                diagnostic.update(
                    failure_category="provider_context_limit", configuration_required=True
                )
            retry_delay = _retry_after_seconds(exc.headers)
            if retry_delay is not None:
                diagnostic["retry_after_seconds"] = retry_delay
            if exhausted or exc.code in (408, 504, 429):
                break
            if exc.code < 500 and exc.code != 429:
                break
        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            http.client.HTTPException,
        ) as exc:
            last_error = type(exc).__name__
            diagnostic = {
                "failure_category": "transport_timeout"
                if isinstance(exc, TimeoutError)
                or isinstance(getattr(exc, "reason", None), TimeoutError)
                else "connection_failed",
                "phase": transport_phase,
                "elapsed_seconds": round(time.perf_counter() - attempt_start, 3),
                "connect_timeout_seconds": timeout,
                "stream_idle_timeout_seconds": idle_timeout,
                "stream_total_timeout_seconds": total_timeout,
                **getattr(exc, "response_diagnostic", {}),
            }
            import errno
            import socket

            reason = getattr(exc, "reason", exc)
            if transport_phase == "connect_or_headers" and (
                isinstance(reason, socket.gaierror)
                or isinstance(reason, OSError)
                and reason.errno
                in {
                    errno.ECONNREFUSED,
                    errno.ENETUNREACH,
                    errno.EHOSTUNREACH,
                    errno.EACCES,
                    errno.EPERM,
                }
            ):
                diagnostic["request_not_sent"] = True
            # A disconnected/timeout POST may already have incurred inference.
            # Preserve pending work instead of blindly posting the same prompt.
            break
        finally:
            if observer:
                observer.emit(
                    "transport_attempt",
                    attempt_status,
                    attempt=attempt + 1,
                    http_status=attempt_code,
                    duration_seconds=time.perf_counter() - attempt_start,
                )
        if attempt < retries:
            delay = retry_delay or min(2**attempt, 8)
            if observer:
                observer.emit("transport_backoff", duration_seconds=delay, attempt=attempt + 1)
            time.sleep(delay)
    # Never include URL credentials, request headers, or server response body.
    error = RuntimeError(f"semantic API request failed ({last_error})")
    error.response_diagnostic = {
        **(diagnostic or {"failure_category": "transport_error"}),
        "transport_attempts": attempt + 1,
    }
    raise error
