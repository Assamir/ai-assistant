#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Kopiuje polskie głosy Piper do frontend/resources/piper-voices/pl/pl_PL
.DESCRIPTION
    Domyślnie szuka ..\..\piper-voices\pl\pl_PL przy assystencie w tym samym katalogu nadrzędnym co klon,
    np. antigravity/assystent + antigravity/piper-voices.
#>
param(
    [string] $SourceRoot = "",
    [string] $DestRoot = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
if (-not $DestRoot) {
    $DestRoot = Join-Path $RepoRoot "frontend\resources\piper-voices\pl\pl_PL"
}

if (-not $SourceRoot) {
    $Parent = Split-Path $RepoRoot -Parent
    $SourceRoot = Join-Path $Parent "piper-voices\pl\pl_PL"
}

if (-not (Test-Path $SourceRoot)) {
    Write-Error "Brak źródła: $SourceRoot. Użyj: -SourceRoot 'C:\\sciezka\\do\\piper-voices\\pl\\pl_PL'"
}

New-Item -ItemType Directory -Force -Path $DestRoot | Out-Null
robocopy $SourceRoot $DestRoot /E /NFL /NDL /NJH /NP
if ($LASTEXITCODE -ge 8) {
    Write-Error "robocopy zakończył się kodem $LASTEXITCODE"
}
Write-Host "OK -> $DestRoot"
