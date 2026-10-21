param([string]$BaselineDll = '')
$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    & cargo build -p ct-cuda
    if ($LASTEXITCODE -ne 0) { throw 'CT build failed.' }
    $taskVsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $taskVsRoot = & $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $taskVsRoot) { throw 'MSVC tools unavailable.' }
    $taskVcvars = Join-Path $taskVsRoot 'VC/Auxiliary/Build/vcvars64.bat'
    $taskBuild = '.cache/p05b-build/' + [guid]::NewGuid().ToString('N')
    New-Item -ItemType Directory -Force -Path $taskBuild | Out-Null
    $taskBuildWin = $taskBuild.Replace('/', '\')
    $taskExports = [regex]::Matches((Get-Content -Raw 'include/ct_cuda.h'), ' X\((cu\w+),') | ForEach-Object { '    ' + $_.Groups[1].Value }
    @('LIBRARY nvcuda.dll', 'EXPORTS') + $taskExports | Set-Content -Encoding ascii (Join-Path $taskBuild 'nvcuda.def')
    @('@echo off', ('call "' + $taskVcvars + '" >nul'), 'if errorlevel 1 exit /b 1',
      ('lib /nologo /def:' + $taskBuildWin + '\nvcuda.def /machine:x64 /out:' + $taskBuildWin + '\nvcuda.lib'),
      'if errorlevel 1 exit /b 1',
      ('cl /nologo /W4 /WX /Iinclude tests\p05b_cuda_app.c ' + $taskBuildWin + '\nvcuda.lib /Fo' + $taskBuildWin + '\p05b_static.obj /Fe' + $taskBuildWin + '\p05b_static.exe'),
      'if errorlevel 1 exit /b 1',
      ('cl /nologo /W4 /WX /DDYNAMIC_CUDA /Iinclude tests\p05b_cuda_app.c /Fo' + $taskBuildWin + '\p05b_dynamic.obj /Fe' + $taskBuildWin + '\p05b_dynamic.exe')
    ) | Set-Content -Encoding utf8NoBOM (Join-Path $taskBuild 'build.cmd')
    & cmd.exe /d /c ($taskBuildWin + '\build.cmd')
    if ($LASTEXITCODE -ne 0) { throw 'Reset consumer build failed.' }
    $taskArguments = @('tests/p05b_reset_check.py', $taskBuild)
    if ($BaselineDll) { $taskArguments += @('--baseline-dll', $BaselineDll) }
    & python @taskArguments
    if ($LASTEXITCODE -ne 0) { throw 'Reset consumer verification failed.' }
} finally { Pop-Location }
