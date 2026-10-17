"""Hosted limits must bound inference without changing ordinary local use."""
import asyncio

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main
from app.hosting import InferenceGate, MAX_REQUEST_BYTES

ISSUE = {'issue_text': 'Add clear Windows setup instructions for new contributors.'}


@pytest.fixture
def hosted(monkeypatch):
    monkeypatch.setenv('PUBLIC_MODE', 'true')
    monkeypatch.setenv('MOCK_AI', 'true')
    monkeypatch.setattr(main, 'inference_gate', InferenceGate())
    return TestClient(main.app)


def test_hosted_cooldown_and_health_remain_usable(hosted):
    assert hosted.post('/api/analyze', json=ISSUE).status_code == 200
    response = hosted.post('/api/analyze', json=ISSUE)
    assert response.status_code == 429
    assert 1 <= int(response.headers['retry-after']) <= 31
    assert hosted.get('/health').json()['public_mode'] is True
    assert hosted.get('/').status_code == 200


def test_hosted_model_choice_and_invalid_input_do_not_use_capacity(hosted):
    assert hosted.post('/api/analyze', json={**ISSUE, 'model': 'gemma3:1b'}).status_code == 422
    assert hosted.post('/api/analyze', json={}).status_code == 422
    assert hosted.post('/api/analyze', json=ISSUE).status_code == 200


def test_hosted_streaming_body_limit(hosted):
    async def run():
        async def oversized():
            yield b'{"issue_text":"'
            yield b'a' * MAX_REQUEST_BYTES
            yield b'"}'
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post('/api/analyze', content=oversized(),
                                         headers={'Content-Type': 'application/json'})
            assert response.status_code == 413
    asyncio.run(run())
    assert hosted.post('/api/analyze', json=ISSUE).status_code == 200


def test_hosted_rejects_concurrent_generation(hosted, monkeypatch):
    monkeypatch.setenv('MOCK_AI', 'false')

    async def run():
        started = asyncio.Event()
        release = asyncio.Event()

        async def generate(issue, model):
            started.set()
            await release.wait()
            return 'A contribution plan.'

        monkeypatch.setattr(main, 'query_ollama', generate)
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            first = asyncio.create_task(client.post('/api/analyze', json=ISSUE))
            try:
                await asyncio.wait_for(started.wait(), timeout=3)
                second = await client.post('/api/analyze', json=ISSUE)
                assert second.status_code == 429
                assert 'busy' in second.json()['detail']
            finally:
                release.set()
                result = await first
            assert result.status_code == 200
    asyncio.run(run())


def test_failed_inference_releases_shared_capacity(hosted, monkeypatch):
    monkeypatch.setenv('MOCK_AI', 'false')
    monkeypatch.setattr(main, 'inference_gate', InferenceGate(cooldown=0))

    async def fail(issue, model):
        raise HTTPException(503, 'Model offline')

    monkeypatch.setattr(main, 'query_ollama', fail)
    assert hosted.post('/api/analyze', json=ISSUE).status_code == 503
    monkeypatch.setenv('MOCK_AI', 'true')
    assert hosted.post('/api/analyze', json=ISSUE).status_code == 200


def test_local_mode_has_no_shared_cooldown(monkeypatch):
    monkeypatch.delenv('PUBLIC_MODE', raising=False)
    monkeypatch.setenv('MOCK_AI', 'true')
    with TestClient(main.app) as client:
        assert client.post('/api/analyze', json=ISSUE).status_code == 200
        assert client.post('/api/analyze', json=ISSUE).status_code == 200
        assert client.get('/health').json()['public_mode'] is False
