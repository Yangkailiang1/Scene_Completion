"""Validate provider envelopes before the workflow interprets business output."""


class InvalidProviderResponse(RuntimeError):
    def __init__(
        self, reason, *, phase="response_decode", http_status=None, attempts=1, usage=None
    ):
        super().__init__(f"Invalid chat completions response ({reason})")
        self.usage = usage
        self.response_diagnostic = {
            "failure_category": "invalid_provider_response",
            "reason": reason,
            "phase": phase,
            "transport_attempts": attempts,
        }
        if type(http_status) is int:
            self.response_diagnostic["http_status"] = http_status


def invalid_chat_response(value):
    if not isinstance(value, dict):
        return "invalid_envelope"
    if value.get("error") is not None:
        return "provider_error_envelope"
    if "choices" not in value:
        return "missing_choices"
    choices = value["choices"]
    if not isinstance(choices, list) or not all(isinstance(c, dict) for c in choices):
        return "invalid_choices"
    if not choices:
        return "empty_choices"
    choice = choices[0]
    # Preserve the provider's truncation diagnosis even when no content survived.
    if choice.get("finish_reason") == "length":
        return None
    message = choice.get("message")
    if not isinstance(message, dict):
        return "invalid_message"
    content = message.get("content")
    if isinstance(content, list):
        if any(not isinstance(part, dict) for part in content):
            return "invalid_content"
        content = "".join(part["text"] for part in content if isinstance(part.get("text"), str))
    if content is not None and not isinstance(content, str):
        return "invalid_content"
    calls = message.get("tool_calls")
    if calls is not None:
        if not isinstance(calls, list) or any(
            not isinstance(call, dict)
            or not isinstance(call.get("function"), dict)
            or not isinstance(call.get("id"), str)
            or not call["id"]
            or not isinstance(call["function"].get("name"), str)
            or not call["function"]["name"]
            or not isinstance(call["function"].get("arguments"), str)
            for call in calls
        ):
            return "invalid_tool_calls"
    if not content and not calls:
        return "empty_message"
    return None
