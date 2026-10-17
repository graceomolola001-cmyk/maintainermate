"""Download only qwen3:1.7b while building the image, not on each visitor request."""
import subprocess

from serve import MODEL, wait_for_ollama

process = subprocess.Popen(['ollama', 'serve'])
try:
    wait_for_ollama(process)
    subprocess.run(['ollama', 'pull', MODEL], check=True)
    if MODEL not in wait_for_ollama(process):
        raise RuntimeError('Model pull finished without the required model being available.')
finally:
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
