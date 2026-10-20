$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    & cargo build -p ct-cuda
    if ($LASTEXITCODE -ne 0) { throw 'CT DLL build failed.' }
    & python tests/m3o_immediates_check.py
    if ($LASTEXITCODE -ne 0) { throw 'M3o native immediate check failed.' }
} finally { Pop-Location }
