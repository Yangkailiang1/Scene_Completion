import io
import json
import urllib.error
import pytest
from scene_completion.review import _post_chat_completions_diagnostic


def test_credit_limit_is_classified_without_retaining_server_body_or_credentials(monkeypatch):
    calls=[]
    secret='private-key-from-local-env'
    def fail(request,timeout):
        calls.append(request)
        raw=json.dumps({'error':{'message':'credits limit per 168 hours; '+secret}}).encode()
        raise urllib.error.HTTPError(request.full_url,429,'limit',{'Retry-After':'120'},io.BytesIO(raw))
    monkeypatch.setattr('urllib.request.urlopen',fail)
    with pytest.raises(RuntimeError) as raised:
        _post_chat_completions_diagnostic('https://example.invalid/chat/completions',secret,{'model':'ecnu-max'},20,2)
    assert len(calls)==1
    diagnostic=raised.value.response_diagnostic
    assert diagnostic=={'http_status':429,'failure_category':'quota_exhausted','retry_after_seconds':60}
    assert secret not in str(raised.value)+json.dumps(diagnostic)


def test_temporary_rate_limit_is_distinct_from_credit_limit(monkeypatch):
    def fail(request,timeout):
        raise urllib.error.HTTPError(request.full_url,429,'limit',{},io.BytesIO(b'{"error":"requests per minute"}'))
    monkeypatch.setattr('urllib.request.urlopen',fail)
    with pytest.raises(RuntimeError) as raised:
        _post_chat_completions_diagnostic('https://example.invalid/chat/completions','secret',{},20,0)
    assert raised.value.response_diagnostic['failure_category']=='rate_limited'
