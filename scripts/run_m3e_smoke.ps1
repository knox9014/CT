param([switch]$SkipCtBuild)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'run_m3c_smoke.ps1') -CompressedFatbin -SkipCtBuild:$SkipCtBuild
if ($LASTEXITCODE -ne 0) { throw 'M3e compressed fatbin smoke failed.' }
