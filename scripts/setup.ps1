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

$Verify = Join-Path $Root "scripts\verify_env.py"
Write-Host ""
Write-Host "Opcjonalnie VLM (Moondream2): ten sam venv, potem:"
Write-Host ('  & "{0}" -m pip install torch transformers accelerate' -f $Py)
Write-Host "Build z CUDA (GPU): https://pytorch.org/get-started/locally/ - patrz docs/ENV_SETUP.md sekcja 4.4"
Write-Host ""
Write-Host "Gotowe. Aktywacja: .\.venv\Scripts\Activate.ps1"
Write-Host ('Weryfikacja:  & "{0}" "{1}"' -f $Py, $Verify)
Write-Host "Dev jednym klikiem (Windows): .\scripts\start-dev.bat"
