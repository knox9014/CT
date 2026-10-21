param([string]$HeaderDirectory = '.cache/reference/cuda-12.0/include',
      [string]$CtDll = 'target/debug/ct_cuda.dll',
      [string]$Lock = 'docs/compatibility/toolchain-lock-v1.json')
$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    $taskHeaderRoot = (Resolve-Path -LiteralPath $HeaderDirectory).Path
    # Check the observed bytes against the recorded package/header pin first.
    & python scripts/check_toolchain_files.py cuda-headers $taskHeaderRoot --lock $Lock
    if ($LASTEXITCODE -ne 0) { throw 'Official CUDA header pin mismatch.' }
    $taskVsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $taskVsRoot = & $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $taskVsRoot) { throw 'MSVC x64 tools unavailable.' }
    $taskVcvars = Join-Path $taskVsRoot 'VC/Auxiliary/Build/vcvars64.bat'
    $taskBuild = '.cache/universal-foundation/abi'
    New-Item -ItemType Directory -Force -Path $taskBuild | Out-Null
    $taskCommands = @('@echo off', ('call "' + $taskVcvars + '" >nul'), 'if errorlevel 1 exit /b 1')
    foreach ($taskProbe in @('cuda_reference_abi', 'cuda_declared_abi', 'cuda_reference_consumer')) {
        $taskCommands += ('cl /nologo /W4 /EHsc /std:c++17 /utf-8 /I"' + $taskHeaderRoot + '" tests\' + $taskProbe + '.cpp /Fo' + $taskBuild + '/' + $taskProbe + '.obj /Fe' + $taskBuild + '/' + $taskProbe + '.exe')
        $taskCommands += 'if errorlevel 1 exit /b 1'
    }
    $taskBatch = Join-Path $taskBuild 'build.cmd'
    $taskCommands | Set-Content -Encoding utf8 $taskBatch
    & cmd.exe /d /c $taskBatch
    if ($LASTEXITCODE -ne 0) { throw 'CUDA ABI probe compilation failed.' }
    $taskReference = & "$taskBuild/cuda_reference_abi.exe"
    if ($LASTEXITCODE -ne 0) { throw 'Reference probe failed.' }
    $taskDeclared = & "$taskBuild/cuda_declared_abi.exe"
    if ($LASTEXITCODE -ne 0) { throw 'Declared probe failed.' }
    $taskReference | Set-Content -Encoding utf8 "$taskBuild/reference.txt"
    $taskDeclared | Set-Content -Encoding utf8 "$taskBuild/declared.txt"
    if (Compare-Object $taskReference $taskDeclared -SyncWindow 0) { throw 'CUDA normalized ABI mismatch; see local probe reports.' }
    $taskDllPath = (Resolve-Path -LiteralPath $CtDll).Path
    & "$taskBuild/cuda_reference_consumer.exe" $taskDllPath
    if ($LASTEXITCODE -ne 0) { throw 'Official PFN consumer failed.' }
    Write-Output 'CUDA ABI: 29 signatures, error/query values and official-PFN consumer passed (Windows x64).'
} finally { Pop-Location }
