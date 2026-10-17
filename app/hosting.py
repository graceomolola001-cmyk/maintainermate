"""Bounds for a small, single-worker public demonstration server."""
from __future__ import annotations

import os
from threading import Lock
import time

from fastapi import HTTPException
from starlette.responses import JSONResponse

MAX_REQUEST_BYTES = 32 * 1024


def public_mode() -> bool:
    return (os.environ.get('PUBLIC_MODE', '').strip().lower() == 'true'
            or os.environ.get('AI_PROVIDER', '').strip().lower() == 'groq')


class InferenceGate:
    """One active request and a minimum interval between admissions per process."""

    def __init__(self, cooldown: int = 30, daily_limit: int = 100):
        self.cooldown = cooldown
        self.daily_limit = daily_limit
        self._day = int(time.time() // 86400)
        self._used = 0
        self._lock = Lock()
        self._active = False
        self._last_start: float | None = None

    def acquire(self) -> None:
        with self._lock:
            if self._active:
                raise HTTPException(429, 'The shared AI server is busy. Please try again shortly.',
                                    headers={'Retry-After': '30'})
            day = int(time.time() // 86400)
            if day != self._day:
                self._day, self._used = day, 0
            if self._used >= self.daily_limit:
                retry = max(1, int((day + 1) * 86400 - time.time()))
                raise HTTPException(429, 'This shared demo has reached its daily limit. Please try again later.',
                                    headers={'Retry-After': str(retry)})
            now = time.monotonic()
            if self._last_start is not None and now - self._last_start < self.cooldown:
                retry = max(1, int(self.cooldown - (now - self._last_start)) + 1)
                raise HTTPException(429, 'Please wait briefly before requesting another plan.',
                                    headers={'Retry-After': str(retry)})
            self._used += 1
            self._last_start = now
            self._active = True

    def release(self) -> None:
        with self._lock:
            self._active = False


class PublicRequestLimit:
    """Bound streamed bodies before FastAPI parses JSON, including chunked requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not (public_mode() and scope['type'] == 'http'
                and scope['path'] == '/api/analyze' and scope['method'] == 'POST'):
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            if len(body) > MAX_REQUEST_BYTES:
                response = JSONResponse({'detail': 'Request is too large. Use a shorter issue description.'},
                                        status_code=413)
                return await response(scope, receive, send)
            if not message.get('more_body', False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        return await self.app(scope, replay, send)
