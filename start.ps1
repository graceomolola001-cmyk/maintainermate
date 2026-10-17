# Run from ANY location: .\start.ps1 (inside the extracted folder).
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.\.venv\Scripts\python.exe')) {
    Write-Host 'Python environment not found. First run: .\setup.ps1' -ForegroundColor Yellow
    exit 1
}
if (-not $env:OLLAMA_MODEL) { $env:OLLAMA_MODEL = 'qwen3:1.7b' }
try {
    $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3
} catch {
    Write-Host 'Ollama is not running. Launch the Ollama app or open another terminal and run: ollama serve' -ForegroundColor Yellow
    exit 1
}
Write-Host "Launching MaintainerMate at http://127.0.0.1:8000 (default: $env:OLLAMA_MODEL)" -ForegroundColor Green
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
