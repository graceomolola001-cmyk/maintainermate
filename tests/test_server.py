"""Exercise a real server process using demo mode; no external services needed."""
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx
import pytest


def test_server_demo_roundtrip(tmp_path):
    root = Path(__file__).resolve().parents[1]
    process_env = os.environ.copy()
    process_env['MOCK_AI'] = 'true'
    log_path = tmp_path / 'server.log'
    # Uvicorn chooses a free port; read the actual bound address from its log.
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host',
             '127.0.0.1', '--port', '0'],
            cwd=root, env=process_env, stdout=log, stderr=log,
        )
        try:
            import re
            deadline = time.monotonic() + 20
            address = None
            while time.monotonic() < deadline:
                output = log_path.read_text(encoding='utf-8')
                match = re.search(r'Uvicorn running on (http://127\.0\.0\.1:\d+)', output)
                if match:
                    address = match.group(1)
                    break
                if process.poll() is not None:
                    pytest.fail(f'Server exited unexpectedly: {output}')
                time.sleep(0.1)
            assert address, log_path.read_text(encoding='utf-8')
            with httpx.Client(base_url=address, trust_env=False, timeout=10) as client:
                for path in ['/', '/static/app.js', '/static/style.css', '/api/docs']:
                    response = client.get(path)
                    assert response.status_code == 200
                    assert response.content
                assert client.get('/health').json()['status'] == 'mock'
                response = client.post('/api/analyze', json={
                    'issue_text': 'The README needs Windows PowerShell setup instructions.'})
                assert response.status_code == 200
                result = response.json()
                assert 'DEMO ONLY' in result['model']
                assert 'IMPLEMENTATION PLAN' in result['analysis']
                assert client.post('/api/analyze', json={}).status_code == 422
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
