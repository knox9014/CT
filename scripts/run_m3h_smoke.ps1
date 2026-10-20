param([switch]$SkipCtBuild)
$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    & python tests/m3c_external_check.py prepare
    if ($LASTEXITCODE -ne 0) { throw 'Pinned CUDA headers/source preparation failed.' }
    if (-not $SkipCtBuild) {
        & cargo build -p ct-cuda
        if ($LASTEXITCODE -ne 0) { throw 'CT DLL build failed.' }
    }
    $taskVsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $taskVsRoot = & $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $taskVsRoot) { throw 'MSVC unavailable.' }
    $taskVcvars = Join-Path $taskVsRoot 'VC/Auxiliary/Build/vcvars64.bat'
    $taskBuild = '.cache/m3h-build/' + [guid]::NewGuid().ToString('N')
    New-Item -ItemType Directory -Force -Path $taskBuild | Out-Null
    $taskWin = $taskBuild.Replace('/', '\')
    $taskExports = [regex]::Matches((Get-Content -Raw 'include/ct_cuda.h'), ' X\((cu\w+),') | ForEach-Object { '    ' + $_.Groups[1].Value }
    @('LIBRARY nvcuda.dll','EXPORTS') + $taskExports | Set-Content -Encoding ascii (Join-Path $taskBuild 'nvcuda.def')
    @('@echo off',('call "' + $taskVcvars + '" >nul'),'if errorlevel 1 exit /b 1',
      ('lib /nologo /def:' + $taskWin + '\nvcuda.def /machine:x64 /out:' + $taskWin + '\nvcuda.lib'),
      'if errorlevel 1 exit /b 1',
      ('cl /nologo /O2 /MD /W4 /utf-8 /D_CRT_SECURE_NO_WARNINGS /I.cache\reference\cuda-12.0\include tests\m3h_cuda_app.c ' + $taskWin + '\nvcuda.lib /Fo' + $taskWin + '\m3h_cuda_app.obj /Fe' + $taskWin + '\m3h_cuda_app.exe')
    ) | Set-Content -Encoding utf8NoBOM (Join-Path $taskBuild 'build.cmd')
    & cmd.exe /d /c ($taskWin + '\build.cmd')
    if ($LASTEXITCODE -ne 0) { throw 'Independent CUDA consumer build failed.' }
    & python tests/m3h_dimensions_check.py $taskBuild
    if ($LASTEXITCODE -ne 0) { throw 'M3h module/GPU/application verification failed.' }
} finally { Pop-Location }
