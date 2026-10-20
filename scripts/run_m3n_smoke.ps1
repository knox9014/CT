$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    & cargo build -p ct-cuda
    if ($LASTEXITCODE -ne 0) { throw 'CT DLL build failed.' }
    & python tests/m3n_minmax_check.py
    if ($LASTEXITCODE -ne 0) { throw 'M3n native min/max/unary check failed.' }
} finally { Pop-Location }
