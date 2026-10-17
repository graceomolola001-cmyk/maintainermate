# Run from normal PowerShell. No models are downloaded by this script.
param([switch]$Demo)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
$previousMock = $env:MOCK_AI
$previousModel = $env:OLLAMA_MODEL
try {
    if (-not (Test-Path '.\.venv\Scripts\python.exe')) {
        throw 'Python environment not found. First run: .\setup.ps1'
    }
    if (-not $env:OLLAMA_MODEL) { $env:OLLAMA_MODEL = 'qwen3:1.7b' }
    if ($Demo) { $env:MOCK_AI = 'true' }
    if ($env:MOCK_AI -ne 'true') {
        try {
            $tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5
        } catch {
            throw 'Ollama is unavailable. Open Ollama or run ollama serve in another terminal, then retry.'
        }
        if (@($tags.models.name) -notcontains $env:OLLAMA_MODEL) {
            throw "Model '$env:OLLAMA_MODEL' is not installed. Run ollama list and select an installed model using `$env:OLLAMA_MODEL. No model was downloaded."
        }
    } else {
        Write-Host 'DEMO ONLY: responses are fixed examples; no AI model is used.' -ForegroundColor Yellow
    }
    Write-Host "Launching MaintainerMate at http://127.0.0.1:8000 (default: $env:OLLAMA_MODEL)" -ForegroundColor Green
    & '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    if ($LASTEXITCODE -ne 0) { throw 'Application startup failed. Check the error above.' }
} finally {
    $env:MOCK_AI = $previousMock
    $env:OLLAMA_MODEL = $previousModel
    Pop-Location
}
