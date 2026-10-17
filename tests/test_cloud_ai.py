"""Provider contracts and failure modes, without real credentials or external calls."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app import cloud_ai
from app.hosting import InferenceGate

ISSUE = {'issue_text': 'Add clear Windows setup instructions for new contributors.'}
TEST_KEY = 'synthetic-test-value'


@pytest.fixture
def groq(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER', 'groq')
    monkeypatch.setenv('GROQ_API_KEY', TEST_KEY)
    monkeypatch.setenv('GROQ_MODEL', cloud_ai.DEFAULT_GROQ_MODEL)
    monkeypatch.delenv('MOCK_AI', raising=False)
    monkeypatch.setattr(main, 'inference_gate', InferenceGate(cooldown=0))
    return TestClient(main.app)


def fake_transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(cloud_ai.httpx, 'AsyncClient', lambda *args, **kwargs:
                        original(*args, transport=httpx.MockTransport(handler), **kwargs))


def test_groq_request_contract_and_provider_attribution(groq, monkeypatch):
    calls = []

    def respond(req):
        calls.append(req)
        assert str(req.url) == cloud_ai.GROQ_CHAT_URL
        assert req.headers['Authorization'] == f'Bearer {TEST_KEY}'
        payload = json.loads(req.content)
        assert payload['model'] == cloud_ai.DEFAULT_GROQ_MODEL
        assert payload['messages'][0]['content'] == main.PROMPT
        assert ISSUE['issue_text'] in payload['messages'][1]['content']
        assert payload['max_completion_tokens'] == 750
        assert payload['stream'] is False
        return httpx.Response(200, json={'choices': [{'message': {'content': 'A real API-shaped plan.'}}]})

    fake_transport(monkeypatch, respond)
    response = groq.post('/api/analyze', json=ISSUE)
    assert response.status_code == 200
    assert response.json()['analysis'] == 'A real API-shaped plan.'
    assert response.json()['provider'] == 'groq'
    assert response.json()['model'] == cloud_ai.DEFAULT_GROQ_MODEL
    assert TEST_KEY not in response.text
    assert len(calls) == 1


def test_groq_health_and_readiness_do_not_call_or_expose_key(groq, monkeypatch):
    def unexpected(req):
        pytest.fail('Readiness must not consume a model request.')
    fake_transport(monkeypatch, unexpected)
    response = groq.get('/health')
    assert response.json()['status'] == 'api_configured'
    assert response.json()['provider'] == 'groq'
    assert response.json()['public_mode'] is True
    assert TEST_KEY not in response.text
    assert TEST_KEY not in groq.get('/').text
    assert TEST_KEY not in groq.get('/static/app.js').text
    assert groq.get('/ready').status_code == 200


def test_groq_missing_key_is_an_explicit_error(groq, monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY')
    assert groq.get('/health').json()['status'] == 'api_key_missing'
    assert groq.get('/ready').status_code == 503
    response = groq.post('/api/analyze', json=ISSUE)
    assert response.status_code == 503
    assert 'DEMO ONLY' not in response.text


def test_groq_client_cannot_switch_models(groq, monkeypatch):
    def unexpected(req):
        pytest.fail('An unconfigured model must not reach the provider.')
    fake_transport(monkeypatch, unexpected)
    response = groq.post('/api/analyze', json={**ISSUE, 'model': 'another-paid-model'})
    assert response.status_code == 422


@pytest.mark.parametrize('status,expected', [(400, 503), (401, 503), (403, 503),
                                            (402, 503), (404, 503), (429, 429),
                                            (500, 502), (302, 502)])
def test_groq_http_failures_are_private_and_not_retried(groq, monkeypatch, status, expected):
    calls = []
    def respond(req):
        calls.append(req)
        return httpx.Response(status, json={'error': TEST_KEY}, headers={
            'Retry-After': '12', 'Location': 'https://untrusted.invalid/'})
    fake_transport(monkeypatch, respond)
    response = groq.post('/api/analyze', json=ISSUE)
    assert response.status_code == expected
    assert TEST_KEY not in response.text
    assert len(calls) == 1
    if status == 429:
        assert response.headers['Retry-After'] == '12'


@pytest.mark.parametrize('data', [{}, {'choices': []}, {'choices': [None]},
                                  {'choices': [{'message': {'content': ''}}]},
                                  {'choices': [{'message': {'content': 42}}]}])
def test_groq_malformed_response(groq, monkeypatch, data):
    fake_transport(monkeypatch, lambda req: httpx.Response(200, json=data))
    assert groq.post('/api/analyze', json=ISSUE).status_code == 502


@pytest.mark.parametrize('error,status', [(httpx.ReadTimeout, 504), (httpx.ConnectError, 502)])
def test_groq_network_failures(groq, monkeypatch, error, status):
    def fail(req):
        raise error('synthetic upstream error', request=req)
    fake_transport(monkeypatch, fail)
    assert groq.post('/api/analyze', json=ISSUE).status_code == status


def test_groq_limits_apply_even_when_public_mode_is_disabled(groq, monkeypatch):
    monkeypatch.setenv('PUBLIC_MODE', 'false')
    monkeypatch.setenv('MOCK_AI', 'true')
    monkeypatch.setattr(main, 'inference_gate', InferenceGate())
    assert groq.post('/api/analyze', json=ISSUE).status_code == 200
    assert groq.post('/api/analyze', json=ISSUE).status_code == 429


def test_shared_daily_budget_resets_at_utc_day_boundary(monkeypatch):
    from app import hosting
    clock = [100000.0]
    monkeypatch.setattr(hosting.time, 'time', lambda: clock[0])
    gate = InferenceGate(cooldown=0, daily_limit=1)
    gate.acquire()
    gate.release()
    with pytest.raises(main.HTTPException) as error:
        gate.acquire()
    assert error.value.status_code == 429
    assert 'daily limit' in error.value.detail
    clock[0] += 86400
    gate.acquire()
    gate.release()


def test_unknown_provider_fails_instead_of_silent_fallback(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER', 'unknown')
    with TestClient(main.app) as client:
        assert client.get('/ready').status_code == 503
        assert client.post('/api/analyze', json=ISSUE).status_code == 503


def test_invalid_issue_url_does_not_consume_daily_budget(groq, monkeypatch):
    monkeypatch.setattr(main, 'inference_gate', InferenceGate(cooldown=0, daily_limit=1))
    fake_transport(monkeypatch, lambda req: httpx.Response(200, json={
        'choices': [{'message': {'content': 'A useful plan.'}}]}))
    invalid = groq.post('/api/analyze', json={'github_url': 'https://untrusted.invalid/issues/1'})
    assert invalid.status_code == 422
    assert groq.post('/api/analyze', json=ISSUE).status_code == 200
