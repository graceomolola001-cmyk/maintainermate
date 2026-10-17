# Run from normal PowerShell; activation and administrator access are unnecessary.
param([switch]$Dev)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path '.\.venv\Scripts\python.exe')) {
        if (Get-Command python -ErrorAction SilentlyContinue) {
            & python -m venv .venv
        } elseif (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3 -m venv .venv
        } else {
            throw 'Python is missing. Install Python 3.10+ for your user account, then rerun setup.'
        }
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path '.\.venv\Scripts\python.exe')) {
            throw 'Virtual environment creation failed. Check the error above. Use a writable extracted folder; do not run as administrator or delete an existing environment blindly.'
        }
    }
    $requirements = if ($Dev) { 'requirements-dev.txt' } else { 'requirements.txt' }
    & '.\.venv\Scripts\python.exe' -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the pip error above.' }
    Write-Host 'Setup complete. Run .\start.ps1 to launch MaintainerMate.' -ForegroundColor Green
} finally {
    Pop-Location
}
