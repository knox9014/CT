param([Parameter(Mandatory)][ValidateSet('cpu','validator','producer','arc','combined')][string]$Lane,
      [switch]$Required,
      [string]$OutputDirectory = 'results/local/validation',
      [string]$Validator = '.cache/universal-foundation/spirv-build/tools/Release/spirv-val.exe',
      [string]$Lock = 'docs/compatibility/toolchain-lock-v1.json')
$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    $taskArgs = @('scripts/run_validation.py','--lane',$Lane,'--output-directory',$OutputDirectory,
                  '--validator',$Validator,'--lock',$Lock)
    if ($Required) { $taskArgs += '--required' }
    & python @taskArgs
    if ($LASTEXITCODE -ne 0) { throw 'Validation lane did not pass; inspect ignored local reports.' }
} finally { Pop-Location }
