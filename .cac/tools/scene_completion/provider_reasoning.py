"""Extract only provider-supplied readable reasoning; never infer hidden text."""


def fragments(delta):
    if not isinstance(delta, dict):
        return [], []
    fields = [key for key in ('reasoning_content', 'reasoning', 'reasoning_details') if delta.get(key) is not None]
    # Some gateways duplicate one fragment under two aliases. Prefer the
    # canonical field; never append both aliases to the same reasoning stream.
    for key in fields:
        value = delta[key]
        if isinstance(value, str) and value:
            return [(key, value)], fields
        if isinstance(value, list):
            pieces = []
            for item in value:
                if not isinstance(item, dict) or item.get('type') in {'reasoning.encrypted', 'encrypted'}:
                    continue
                text = item.get('text') or item.get('summary')
                if isinstance(text, str) and text:
                    pieces.append((key, text))
            if pieces:
                return pieces, fields
    return [], fields


def buffered_response(value, *, capture=False, display=False):
    """A JSON response is observable only after it arrives, never live SSE."""
    from .execution_events import emit
    pieces = []; fields = set()
    for choice in value.get('choices', []) or []:
        if choice.get('index', 0) != 0:
            continue
        message = choice.get('message') or {}
        part, names = fragments(message)
        pieces.extend(part); fields.update(names)
        for key in ('reasoning_content', 'reasoning', 'reasoning_details'):
            message.pop(key, None)
        if capture and part:
            message['reasoning_content'] = ''.join(text for _, text in part)
    size = sum(len(text.encode('utf8')) for _, text in pieces)
    value.setdefault('_scene_completion_metrics', {}).update(response_mode='buffered_json', reasoning_bytes=size, reasoning_fields=sorted(fields), reasoning_display_enabled=display)
    emit('stream_status', status='buffered_response', message='网关返回完整JSON而非SSE；只能在响应完成后显示，无法实时展示生成过程。')
    if display:
        for source, text in pieces:
            emit('stream_delta', channel='reasoning', text=text, source='provider_'+source, not_artifact=True, buffered=True)
    return value
