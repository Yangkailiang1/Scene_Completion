"""Estimate final chat context independently of billing quota reservations."""

import json
import math

from scene_completion.models.budgets.context_tokenizer import count_text, resolve_encoding

DEFAULT_LIMIT = 200000


def estimate(body, config=None):
    requested = (config or {}).get("context_tokenizer", "auto")
    encoding, name, basis = resolve_encoding(body.get("model"), requested)
    margin = (0.05 if basis == "model_encoding" else 0.10) if encoding is not None else 0
    framing = 24 if encoding is not None else 256

    def count(text):
        return count_text(encoding, text) if encoding is not None else len(text.encode("utf8"))

    def stringify(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    messages = []
    for message in body.get("messages", []):
        content = message.get("content")
        tokens = count(stringify({k: v for k, v in message.items() if k != "content"}))
        tokens += count(content if isinstance(content, str) else stringify(content))
        messages.append(
            {
                "index": len(messages),
                "role": message.get("role"),
                "estimated_tokens": tokens,
                # Retained for older prompt diagnostics consumers.
                "upper_bound": math.ceil(tokens * (1 + margin)) + framing,
            }
        )
    metadata_tokens = count(
        stringify(
            {
                k: v
                for k, v in body.items()
                if k not in {"messages", "max_tokens", "max_completion_tokens"}
            }
        )
    )
    metadata_budget = math.ceil(metadata_tokens * (1 + margin)) + (
        64 if encoding is not None else 0
    )
    admission_tokens = sum(m["upper_bound"] for m in messages) + metadata_budget
    reserve = body.get("max_tokens", body.get("max_completion_tokens"))
    return {
        "request_bytes": len(json.dumps(body, ensure_ascii=False).encode("utf8")),
        "estimated_input_tokens": sum(m["estimated_tokens"] for m in messages) + metadata_tokens,
        "input_budget_tokens": admission_tokens,
        "estimated_input_tokens_upper_bound": admission_tokens,
        "output_reserve": reserve,
        "context_tokenizer": name if encoding is not None else "utf8_bytes",
        "tokenizer_basis": basis,
        "requested_context_tokenizer": requested,
        "tokenizer_margin_percent": round(margin * 100),
        "estimate_method": (
            "Local BPE tokenization plus margin for chat framing; provider usage may differ"
            if encoding is not None
            else "UTF-8 bytes plus chat framing; conservative fallback, not tokenizer output"
        ),
        "messages": messages,
        "metadata_and_tools_upper_bound": metadata_budget,
    }


def check(body, config):
    limit = config.get("max_context_tokens", DEFAULT_LIMIT)
    if type(limit) is not int or limit < 1:
        raise ValueError("max_context_tokens must be a positive integer")
    value = estimate(body, config)
    value["max_context_tokens"] = limit
    if value["input_budget_tokens"] + value["output_reserve"] > limit:
        error = RuntimeError(
            "task context exceeds configured budget; split scoped task without truncating evidence"
        )
        error.response_diagnostic = {
            "failure_category": "context_budget_exceeded",
            "configuration_required": True,
            "not_sent": True,
            **value,
        }
        raise error
    return value
