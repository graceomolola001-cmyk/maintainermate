"""MaintainerMate: issue planning with local Ollama or server-side Groq.

Local: uvicorn app.main:app --host 127.0.0.1 --port 8000
For the hosted Groq version, see docs/hosting.md.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.cloud_ai import ai_provider, groq_configured, groq_model, query_groq
from app.hosting import InferenceGate, PublicRequestLimit, public_mode

APP_DIR = Path(__file__).resolve().parent
DEMO_PLAN = json.loads((APP_DIR / "demo-plan.json").read_text(encoding="utf-8"))
DEFAULT_MODEL = "qwen3:1.7b"
OLLAMA_URL = "http://127.0.0.1:11434"
ISSUE_URL_RE = re.compile(r"^/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/issues/([0-9]+)/?$", re.I)
MODEL_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,100}$")

app = FastAPI(title="MaintainerMate AI", version="0.3.0", docs_url="/api/docs")
app.add_middleware(PublicRequestLimit)
inference_gate = InferenceGate()
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")


class AnalyzeRequest(BaseModel):
    github_url: str = Field(default="", max_length=300)
    issue_text: str = Field(default="", max_length=6000)
    model: str = Field(default="", max_length=100)


class AnalyzeResponse(BaseModel):
    analysis: str
    model: str
    issue_source: str
    provider: str = "ollama"


def default_model() -> str:
    if ai_provider() == "groq":
        return groq_model()
    return os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def ollama_url() -> str:
    # A fixed local service prevents this app from becoming a proxy to arbitrary hosts.
    return OLLAMA_URL


def parse_github_issue_url(url: str) -> tuple[str, str, int]:
    """Reject unexpected hosts and routes before reaching the public GitHub API."""
    parsed = urlparse(url.strip())
    if (parsed.scheme != "https" or parsed.netloc.lower() not in {"github.com", "www.github.com"}
            or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment):
        raise ValueError("Use a public issue URL, such as https://github.com/owner/repo/issues/123")
    match = ISSUE_URL_RE.fullmatch(parsed.path)
    if not match:
        raise ValueError("Expected a GitHub issue URL ending in /owner/repo/issues/number")
    owner, repo, number = match.groups()
    return owner, repo, int(number)


async def fetch_public_issue(url: str) -> str:
    try:
        owner, repo, number = parse_github_issue_url(url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
            response = await client.get(api_url, headers={
                "Accept": "application/vnd.github+json", "User-Agent": "MaintainerMate-local-demo"
            })
            response.raise_for_status()
            issue = response.json()
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code == 404:
            raise HTTPException(404, "Issue not found or repository is private.") from exc
        if code in (403, 429):
            raise HTTPException(429, "GitHub API rate limit reached. Paste the issue text instead.") from exc
        raise HTTPException(502, "GitHub couldn't retrieve that issue. Paste its text instead.") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(502, "GitHub is unreachable. Paste the issue text instead.") from exc

    if not isinstance(issue, dict):
        raise HTTPException(502, "Unexpected response from GitHub.")
    if "pull_request" in issue:
        raise HTTPException(422, "That link points to a pull request. Please choose a GitHub issue.")
    raw_labels = issue.get("labels") or []
    if not isinstance(raw_labels, list):
        raw_labels = []
    labels = ", ".join(str(v.get("name", "")) for v in raw_labels if isinstance(v, dict))[:250]
    return (f"Repository: {owner}/{repo}\n"
            f"Title: {str(issue.get('title') or '')[:500]}\n"
            f"Labels: {labels}\n"
            f"Body:\n{str(issue.get('body') or '(No issue description)')[:5300]}")


PROMPT = json.loads((APP_DIR / "prompt.json").read_text(encoding="utf-8"))["system_prompt"]


def select_model(value: str) -> str:
    name = value.strip() or default_model()
    if not MODEL_RE.fullmatch(name):
        raise HTTPException(422, "Invalid AI model name.")
    if (ai_provider() == "groq" or public_mode()) and name != default_model():
        raise HTTPException(422, "This shared server only supports its configured model.")
    return name


async def installed_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            res = await client.get(f"{ollama_url()}/api/tags")
            res.raise_for_status()
            data = res.json()
        return [item["name"] for item in data.get("models", [])
                if isinstance(item, dict) and isinstance(item.get("name"), str)]
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError, TypeError, AttributeError):
        raise HTTPException(503, "Ollama is unavailable. Open Ollama or run ollama serve.") from None


async def query_ollama(issue: str, model: str) -> str:
    # Qwen3 has a reasoning mode; disabling it keeps output snappy on 8 GB RAM.
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": f"Analyze the following issue:\n<issue>\n{issue}\n</issue>"},
        ],
        "stream": False,
        "options": {"temperature": 0.3, "num_ctx": 3072, "num_predict": 750},
        "keep_alive": "2m",
    }
    if public_mode():
        body["options"]["num_thread"] = 2
    if model.lower().startswith("qwen3:"):
        body["think"] = False
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=5), trust_env=False) as client:
            res = await client.post(f"{ollama_url()}/api/chat", json=body)
            res.raise_for_status()
            output = res.json()["message"]["content"]
        if not isinstance(output, str) or not output.strip():
            raise ValueError("empty output")
        return output.strip()[:12000]
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(502, f"Model '{model}' isn't installed. Run: ollama pull {model}") from exc
        raise HTTPException(502, f"Ollama returned HTTP {exc.response.status_code}. Check Ollama logs.") from exc
    except httpx.ConnectError as exc:
        raise HTTPException(503, "Ollama is offline. Open Ollama or run ollama serve.") from exc
    except httpx.TimeoutException as exc:
        detail = ("The shared AI server timed out. Please try again later." if public_mode()
                  else "Model response timed out. Close heavy apps or choose a smaller model.")
        raise HTTPException(504, detail) from exc
    except (httpx.RequestError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise HTTPException(502, "Ollama returned an invalid response. Try again or switch models.") from exc


@app.get("/", include_in_schema=False)
async def homepage():
    return FileResponse(APP_DIR / "static" / "index.html")


@app.get("/health")
async def health():
    """Return status and model choices for the model selector, without running inference."""
    provider = ai_provider()
    selected = select_model("")
    if os.environ.get("MOCK_AI", "").lower() == "true":
        return {"status": "mock", "default_model": selected, "models": [], "ollama": "not_required", "public_mode": public_mode(), "provider": "demo"}
    if provider == "groq":
        return {"status": "api_configured" if groq_configured() else "api_key_missing",
                "default_model": selected, "models": [selected], "ollama": "not_required",
                "public_mode": True, "provider": "groq"}
    try:
        models = await installed_models()
        if public_mode():
            models = [name for name in models if name == selected]
        return {"status": "ready" if models else "model_missing",
                "default_model": selected, "models": models, "ollama": "online", "public_mode": public_mode(), "provider": "ollama"}
    except HTTPException:
        return {"status": "ollama_offline", "default_model": selected, "models": [], "ollama": "offline", "public_mode": public_mode(), "provider": "ollama"}


@app.get("/ready", include_in_schema=False)
async def readiness():
    provider = ai_provider()
    select_model("")
    if provider == "groq" and not groq_configured():
        raise HTTPException(503, "The server API key has not been configured.")
    return {"status": "configured", "provider": provider}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest):
    issue_url, pasted = payload.github_url.strip(), payload.issue_text.strip()
    if not issue_url and not pasted:
        raise HTTPException(422, "Enter issue text or a public GitHub issue URL.")
    if issue_url and pasted:
        raise HTTPException(422, "Choose either a GitHub URL or issue text.")
    if pasted and len(pasted) < 20:
        raise HTTPException(422, "Write at least 20 characters describing the issue.")
    if issue_url:
        try:
            parse_github_issue_url(issue_url)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
    provider = ai_provider()
    model = select_model(payload.model)
    mocked = os.environ.get("MOCK_AI", "").lower() == "true"
    if provider == "groq" and not mocked and not groq_configured():
        raise HTTPException(503, "AI is not configured yet. The app owner needs to add the server API key.")
    shared = public_mode()
    if shared:
        inference_gate.acquire()
    try:
        issue = await fetch_public_issue(issue_url) if issue_url else pasted
        source = "Public GitHub issue" if issue_url else "Pasted issue text"

        if os.environ.get("MOCK_AI", "").lower() == "true":
            return AnalyzeResponse(
                model=DEMO_PLAN["model"], issue_source=source, analysis=DEMO_PLAN["analysis"], provider="demo",
            )

        output = (await query_groq(issue, model, PROMPT) if provider == "groq"
                  else await query_ollama(issue, model))
        return AnalyzeResponse(analysis=output, model=model, issue_source=source, provider=provider)
    finally:
        if shared:
            inference_gate.release()
