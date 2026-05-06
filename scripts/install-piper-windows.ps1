#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Pobiera Piper (Windows amd64, release 2023.11.14-2) do tools/piper/.
.DESCRIPTION
    Po instalacji ustaw ścieżki w config/config.yaml (domyślne są względne repo) lub ustaw zmienne ASSY_TTS_*.
#>
param(
    [string] $VersionTag = "2023.11.14-2"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$DestDir = Join-Path $RepoRoot "tools\piper"
$ZipPath = Join-Path $RepoRoot "tools\piper-windows-amd64.zip"
$Url = "https://github.com/rhasspy/piper/releases/download/$VersionTag/piper_windows_amd64.zip"

New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
Write-Host "Pobieram: $Url"
Invoke-WebRequest -Uri $Url -OutFile $ZipPath -UseBasicParsing
Expand-Archive -LiteralPath $ZipPath -DestinationPath $DestDir -Force
Remove-Item -LiteralPath $ZipPath -Force

$Exe = Join-Path $DestDir "piper\piper.exe"
if (-not (Test-Path $Exe)) {
    Write-Error "Oczekiwano $Exe po rozpakowaniu archiwum."
}

Write-Host "OK — binary: $Exe"
Write-Host 'Upewnij się, że config/config.yaml wskazuje piper_voice_onnx_path oraz piper_executable (względnie lub absolutnie od korzenia repo).'
