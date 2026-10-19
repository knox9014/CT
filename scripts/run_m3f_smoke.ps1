param([switch]$SkipCtBuild)
$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    if (-not $SkipCtBuild) {
        & cargo build -p ct-cuda
        if ($LASTEXITCODE -ne 0) { throw 'CT DLL build failed.' }
    }
    & python tests/m3f_selection_check.py
    if ($LASTEXITCODE -ne 0) { throw 'M3f native selection verification failed.' }
    & (Join-Path $PSScriptRoot 'run_m3e_smoke.ps1') -SkipCtBuild
    if ($LASTEXITCODE -ne 0) { throw 'Official sample regression failed.' }
    & (Join-Path $PSScriptRoot 'run_m3c_smoke.ps1') -SkipCtBuild -AlternativeFatbin
    if ($LASTEXITCODE -ne 0) { throw 'Official sample alternative-fatbin verification failed.' }
} finally { Pop-Location }
