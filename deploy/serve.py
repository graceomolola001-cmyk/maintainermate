"""Supervise the private Ollama service and public FastAPI service in one container."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.request import build_opener, ProxyHandler
import json

MODEL = 'qwen3:1.7b'
LOCAL_URL = 'http://127.0.0.1:11434'


def wait_for_ollama(process: subprocess.Popen, timeout: int = 90) -> list[str]:
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('Ollama exited before becoming ready.')
        try:
            with opener.open(f'{LOCAL_URL}/api/tags', timeout=2) as response:
                return [item['name'] for item in json.load(response).get('models', [])]
        except OSError:
            time.sleep(0.25)
    raise RuntimeError('Ollama did not become ready in time.')


def main() -> int:
    # Fixed internal endpoint: the Ollama API is never exposed by this container.
    os.environ['OLLAMA_HOST'] = '127.0.0.1:11434'
    os.environ['OLLAMA_MODEL'] = MODEL
    children = []

    def stopping(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stopping)
    signal.signal(signal.SIGINT, stopping)
    try:
        ollama = subprocess.Popen(['ollama', 'serve'])
        children.append(ollama)
        if MODEL not in wait_for_ollama(ollama):
            raise RuntimeError(f'{MODEL} is absent. Rebuild the image with the model cache step enabled.')
        uvicorn = subprocess.Popen([
            sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0',
            '--port', '7860', '--workers', '1', '--limit-concurrency', '32', '--no-access-log',
        ], cwd=Path(__file__).resolve().parents[1])
        children.append(uvicorn)
        while all(child.poll() is None for child in children):
            time.sleep(0.25)
        raise RuntimeError('An application service exited; stopping the container.')
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
