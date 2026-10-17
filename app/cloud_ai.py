"""Groq integration. Credentials remain server-side and upstream errors stay private."""
from __future__ import annotations

import os

import httpx
from fastapi import HTTPException

DEFAULT_GROQ_MODEL = 'openai/gpt-oss-20b'
GROQ_CHAT_URL = 'https://api.groq.com/openai/v1/chat/completions'


def ai_provider() -> str:
    provider = os.environ.get('AI_PROVIDER', 'ollama').strip().lower()
    if provider not in {'ollama', 'groq'}:
        raise HTTPException(503, 'The AI provider setting is invalid. Please contact the app owner.')
    return provider


def groq_model() -> str:
    return os.environ.get('GROQ_MODEL', DEFAULT_GROQ_MODEL).strip() or DEFAULT_GROQ_MODEL


def groq_configured() -> bool:
    return bool(os.environ.get('GROQ_API_KEY', '').strip())


async def query_groq(issue: str, model: str, prompt: str) -> str:
    key = os.environ.get('GROQ_API_KEY', '').strip()
    if not key:
        raise HTTPException(503, 'AI is not configured yet. The app owner needs to add the server API key.')
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': f'Analyze the following issue:\n<issue>\n{issue}\n</issue>'},
        ],
        'temperature': 0.3,
        'max_completion_tokens': 750,
        'stream': False,
    }
    try:
        # Keep proxy/TLS support; never forward this credential through redirects.
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10),
                                     follow_redirects=False) as client:
            response = await client.post(GROQ_CHAT_URL, json=body, headers={
                'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
            })
        if response.status_code == 429:
            raw_retry = response.headers.get('Retry-After', '')
            retry = str(min(max(int(raw_retry), 1), 3600)) if raw_retry.isdecimal() and len(raw_retry) <= 6 else '60'
            raise HTTPException(429, 'The AI service usage limit has been reached. Please try again later.',
                                headers={'Retry-After': retry})
        if response.status_code in {401, 403}:
            raise HTTPException(503, 'The AI service credentials need attention from the app owner.')
        if response.status_code in {400, 402, 404}:
            raise HTTPException(503, 'The AI model or account is unavailable. Please contact the app owner.')
        if not 200 <= response.status_code < 300:
            raise HTTPException(502, 'The AI service is temporarily unavailable. Please try again later.')
        output = response.json()['choices'][0]['message']['content']
        if not isinstance(output, str) or not output.strip():
            raise ValueError('empty model output')
        return output.strip()[:12000]
    except httpx.TimeoutException:
        raise HTTPException(504, 'The AI service timed out. Please try again later.') from None
    except httpx.RequestError:
        raise HTTPException(502, 'The AI service could not be reached. Please try again later.') from None
    except (ValueError, KeyError, IndexError, TypeError):
        raise HTTPException(502, 'The AI service returned an invalid response. Please try again later.') from None
