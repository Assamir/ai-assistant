# Setup venv i instalacja zależności backendu (Windows PowerShell).
# Uruchom z katalogu głównego repozytorium: .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python nie znaleziony w PATH. Zainstaluj Python 3.11+."
}

$Venv = Join-Path $Root ".venv"
if (-not (Test-Path $Venv)) {
    python -m venv $Venv
}

$Py = Join-Path $Venv "Scripts\python.exe"
& $Py -m pip install --upgrade pip
& $Py -m pip install -r (Join-Path $Root "requirements.txt")

Write-Host "Gotowe. Aktywacja: .\.venv\Scripts\Activate.ps1"
Write-Host "Weryfikacja: python scripts/verify_env.py"
