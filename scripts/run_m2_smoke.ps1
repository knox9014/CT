$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    & cargo build -p ct-cuda
    if ($LASTEXITCODE -ne 0) { throw 'CT DLL build failed.' }
    $taskVsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $taskVsRoot = & $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $taskVsRoot) { throw 'MSVC x64 tools unavailable.' }
    $taskVcvars = Join-Path $taskVsRoot 'VC/Auxiliary/Build/vcvars64.bat'
    New-Item -ItemType Directory -Force -Path '.cache/reference' | Out-Null
    @('@echo off', ('call "' + $taskVcvars + '" >nul'), 'if errorlevel 1 exit /b 1',
      'cl /nologo /W4 /Iinclude tests\m2_kernel_host.c /Fo.cache\reference\m2_host.obj /Fe.cache\reference\m2_host.exe'
    ) | Set-Content -Encoding utf8NoBOM '.cache/reference/build-m2-host.cmd'
    & cmd.exe /d /c .cache\reference\build-m2-host.cmd
    if ($LASTEXITCODE -ne 0) { throw 'C kernel host build failed.' }
    $taskDll = (Resolve-Path -LiteralPath 'target/debug/ct_cuda.dll').Path
    $taskFixtures = (Resolve-Path -LiteralPath 'tests/fixtures').Path
    & '.\.cache\reference\m2_host.exe' $taskDll $taskFixtures
    if ($LASTEXITCODE -ne 0) { throw 'M2 PTX kernel verification failed.' }
} finally {
    Pop-Location
}
