# Naprawa frontend/node_modules na Windows (blokada EBUSY: electron dist/resources/default_app.asar).
# Uruchom z katalogu glownego repozytorium: .\scripts\repair-frontend-node-modules.ps1
#
# Opcjonalnie: zmienna ASSYSTENT_FALLBACK_NODE_MODULES = pelna sciezka do sprawdzonych node_modules.

param(
    [string] $FallbackNodeModules = $env:ASSYSTENT_FALLBACK_NODE_MODULES
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Root "frontend"
$Nm = Join-Path $Frontend "node_modules"

function Stop-ElectronLikeProcesses {
    Get-Process -Name "electron" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process | Where-Object { $_.ProcessName -like "Assystent*" } | Stop-Process -Force -ErrorAction SilentlyContinue
}

function Invoke-MirrorEmptyToNodeModules {
    param([string] $Target)
    $empty = Join-Path ([System.IO.Path]::GetTempPath()) ("nm-empty-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $empty | Out-Null
    try {
        cmd /c "robocopy `"$empty`" `"$Target`" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS" | Out-Null
        $code = $LASTEXITCODE
        if ($code -ge 8) { throw "robocopy mirror failed, exit code: $code" }
    }
    finally {
        Remove-Item -LiteralPath $empty -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Sync-FromOptionalFallback {
    param([string] $Dest)
    $src = $FallbackNodeModules.Trim()
    if (-not $src) {
        $cand = Join-Path $env:TEMP "assystent-electron-build\frontend\node_modules"
        if (Test-Path (Join-Path $cand ".bin\vite.cmd")) {
            $src = $cand
        }
    }
    if (-not $src -or -not (Test-Path $src)) {
        return $false
    }
    Write-Host ("Uzupelnianie node_modules z: {0}" -f $src)
    cmd /c "robocopy `"$src`" `"$Dest`" /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NC /NS" | Out-Null
    $code = $LASTEXITCODE
    if ($code -ge 8) { throw "robocopy sync failed, exit code: $code" }
    return $true
}

Stop-ElectronLikeProcesses
Start-Sleep -Milliseconds 400

Set-Location $Frontend

if (Test-Path $Nm) {
    Write-Host "Czyszczenie node_modules..."
    Remove-Item -LiteralPath $Nm -Recurse -Force -ErrorAction SilentlyContinue
}

if (Test-Path $Nm) {
    Write-Host "Proba oproznienia przez robocopy /MIR..."
    Invoke-MirrorEmptyToNodeModules -Target $Nm
    cmd /c "rmdir /s /q `"$Nm`"" | Out-Null
}

if (Test-Path $Nm) {
    Write-Host "Nie mozna usunac node_modules (plik zablokowany - czesto IDE / AV). Proba uzupelnienia z kopii..."
    $null = Sync-FromOptionalFallback -Dest $Nm
    npm install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host ""
    Write-Host "Gotowe (npm install). npm ci moze nadal padac, dopoki zablokowany jest plik w node_modules\electron."
    Write-Host "Zamknij IDE / proces blokujacy, usun folder frontend\node_modules i uruchom: npm ci"
    exit 0
}

Write-Host "Instalacja (npm ci)..."
npm ci --no-audit --no-fund
if ($LASTEXITCODE -eq 0) {
    Write-Host "Gotowe."
    exit 0
}

Write-Host "npm ci nie powiodlo sie (np. EBUSY); uzupelnianie z kopii i npm install..."
$null = Sync-FromOptionalFallback -Dest $Nm
if (-not (Test-Path (Join-Path $Nm ".bin\vite.cmd"))) {
    throw "Brak npm ci, brak kopii zapasowej. Ustaw ASSYSTENT_FALLBACK_NODE_MODULES lub zbuduj w %TEMP%\assystent-electron-build."
}
npm install --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Gotowe (npm install)."
