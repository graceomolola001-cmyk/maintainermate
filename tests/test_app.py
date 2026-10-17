"""Model-independent tests. They never call a live LLM or the GitHub API."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from app import main

client = TestClient(main.app)


def fake_transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda *args, **kwargs: original(*args, transport=httpx.MockTransport(handler), **kwargs))


def test_home_page_serves_frontend():
    response = client.get("/")
    assert response.status_code == 200
    assert "MaintainerMate AI" in response.text
    assert 'id="model-select"' in response.text


def test_public_issue_url_parser_and_safety():
    assert main.parse_github_issue_url("https://github.com/python/cpython/issues/42") == ("python", "cpython", 42)
    rejected = [
        "http://github.com/a/b/issues/1", "https://evil.com/a/b/issues/1",
        "https://github.com@evil.com/a/b/issues/1", "https://github.com/a/b/pull/1",
        "https://github.com/a/b/issues/1?foo=bar", "https://github.com/a/b/issues/1#comment",
        "https://github.com/a/b/issues/1/more", "https://github.com.evil.com/a/b/issues/1",
        "file:///etc/passwd",
    ]
    for url in rejected:
        with pytest.raises(ValueError):
            main.parse_github_issue_url(url)


def test_invalid_issue_payload():
    assert client.post("/api/analyze", json={}).status_code == 422
    assert client.post("/api/analyze", json={"issue_text": "fix"}).status_code == 422
    assert client.post("/api/analyze", json={"issue_text": "A long valid description of an issue.", "github_url": "https://github.com/a/b/issues/1"}).status_code == 422
    assert client.post("/api/analyze", json={"issue_text": "Correctly formed bug report with repro steps.", "model": "qwen3;rm -rf /"}).status_code == 422


def test_demo_works_without_ollama(monkeypatch):
    monkeypatch.setenv("MOCK_AI", "true")
    health = client.get("/health").json()
    assert health["status"] == "mock"
    response = client.post("/api/analyze", json={"issue_text": "Our README lacks a Windows install section that newcomers can follow."})
    assert response.status_code == 200
    assert "DEMO ONLY" in response.json()["model"]
    assert "IMPLEMENTATION PLAN" in response.json()["analysis"]


def test_health_lists_installed_models(monkeypatch):
    monkeypatch.delenv("MOCK_AI", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:1.7b")
    fake_transport(monkeypatch, lambda req: httpx.Response(200, json={"models": [{"name": "qwen3:1.7b"}, {"name": "gemma3:1b"}]}))
    data = client.get("/health").json()
    assert data["status"] == "ready"
    assert data["models"] == ["qwen3:1.7b", "gemma3:1b"]
    assert data["default_model"] == "qwen3:1.7b"


def test_health_handles_ollama_offline(monkeypatch):
    monkeypatch.delenv("MOCK_AI", raising=False)
    def fail(req):
        raise httpx.ConnectError("down", request=req)
    fake_transport(monkeypatch, fail)
    assert client.get("/health").json()["status"] == "ollama_offline"


def test_chat_payload_qwen_thinking_disabled_and_gemma_switchable(monkeypatch):
    monkeypatch.delenv("MOCK_AI", raising=False)
    calls = []
    def handler(req):
        calls.append((str(req.url), json.loads(req.content)))
        return httpx.Response(200, json={"message": {"content": "1. ISSUE EXPLAINED\nA useful analysis."}})
    fake_transport(monkeypatch, handler)
    for model in ["qwen3:1.7b", "gemma3:1b"]:
        response = client.post("/api/analyze", json={"issue_text": "Write step-by-step Windows setup instructions for new contributors.", "model": model})
        assert response.status_code == 200
        assert response.json()["model"] == model
    assert calls[0][0] == "http://127.0.0.1:11434/api/chat"
    assert calls[0][1]["think"] is False
    assert "think" not in calls[1][1]
    assert calls[0][1]["messages"][0]["role"] == "system"


def test_missing_model_explained(monkeypatch):
    monkeypatch.delenv("MOCK_AI", raising=False)
    fake_transport(monkeypatch, lambda req: httpx.Response(404, json={"error": "missing"}))
    response = client.post("/api/analyze", json={"issue_text": "Windows users cannot install this application using Bash commands.", "model": "gemma3:1b"})
    assert response.status_code == 502
    assert "ollama pull gemma3:1b" in response.json()["detail"]


def test_github_api_support_and_pull_request_rejection(monkeypatch):
    monkeypatch.delenv("MOCK_AI", raising=False)
    urls = []
    def handler(req):
        urls.append(str(req.url))
        if req.url.host == "api.github.com":
            return httpx.Response(200, json={"title": "Fix docs", "body": "This app lacks PowerShell setup steps for Windows contributors.", "labels": [{"name": "docs"}]})
        payload = json.loads(req.content)
        assert "Repository: a/b" in payload["messages"][1]["content"]
        assert "Labels: docs" in payload["messages"][1]["content"]
        return httpx.Response(200, json={"message": {"content": "Clear steps."}})
    fake_transport(monkeypatch, handler)
    response = client.post("/api/analyze", json={"github_url": "https://github.com/a/b/issues/123", "model": "qwen3:1.7b"})
    assert response.status_code == 200
    assert response.json()["issue_source"] == "Public GitHub issue"
    assert urls[0] == "https://api.github.com/repos/a/b/issues/123"


def test_github_pr_disallowed(monkeypatch):
    monkeypatch.delenv("MOCK_AI", raising=False)
    fake_transport(monkeypatch, lambda req: httpx.Response(200, json={"title": "PR", "body": "Something", "pull_request": {"url": "https://api.github.com"}}))
    response = client.post("/api/analyze", json={"github_url": "https://github.com/a/b/issues/123"})
    assert response.status_code == 422
    assert "pull request" in response.json()["detail"]


@pytest.mark.parametrize('path,content_type', [
    ('/static/app.js', 'javascript'),
    ('/static/style.css', 'text/css'),
    ('/api/docs', 'text/html'),
])
def test_frontend_assets_and_docs(path, content_type):
    response = client.get(path)
    assert response.status_code == 200
    assert content_type in response.headers['content-type']
    assert response.content


@pytest.mark.parametrize('url', [
    'https://github.com:443/a/b/issues/1',
    'https://github.com:bad/a/b/issues/1',
    'https://[invalid/a/b/issues/1',
])
def test_malformed_issue_urls_return_validation_error(url):
    response = client.post('/api/analyze', json={'github_url': url})
    assert response.status_code == 422


@pytest.mark.parametrize('response_body', [[], None, {}, {'message': []},
                                          {'message': {'content': ''}},
                                          {'message': {'content': 42}}])
def test_malformed_model_responses_are_reported(monkeypatch, response_body):
    monkeypatch.delenv('MOCK_AI', raising=False)
    fake_transport(monkeypatch, lambda req: httpx.Response(
        200, content=json.dumps(response_body), headers={'Content-Type': 'application/json'}))
    response = client.post('/api/analyze', json={
        'issue_text': 'Windows installation instructions need clearer steps.'})
    assert response.status_code == 502
    assert 'invalid response' in response.json()['detail']


def test_model_timeout_is_reported(monkeypatch):
    monkeypatch.delenv('MOCK_AI', raising=False)
    def timeout(req):
        raise httpx.ReadTimeout('timeout', request=req)
    fake_transport(monkeypatch, timeout)
    response = client.post('/api/analyze', json={
        'issue_text': 'Windows installation instructions need clearer steps.'})
    assert response.status_code == 504


def test_github_unexpected_labels_do_not_crash(monkeypatch):
    monkeypatch.setenv('MOCK_AI', 'true')
    fake_transport(monkeypatch, lambda req: httpx.Response(200, json={
        'title': 'Improve docs', 'body': 'Add clear setup instructions.', 'labels': 42}))
    response = client.post('/api/analyze', json={
        'github_url': 'https://github.com/a/b/issues/1'})
    assert response.status_code == 200
