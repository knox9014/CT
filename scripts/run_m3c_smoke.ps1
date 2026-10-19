param([switch]$SkipCtBuild,[switch]$BinaryFatbin,[switch]$CompressedFatbin,[switch]$AlternativeFatbin)
$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    & python tests/m3c_external_check.py prepare
    if ($LASTEXITCODE -ne 0) { throw 'Pinned CUDA sample preparation failed.' }
    if (-not $SkipCtBuild) {
        & cargo build -p ct-cuda
        if ($LASTEXITCODE -ne 0) { throw 'CT DLL build failed.' }
    }
    $taskVsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $taskVsRoot = & $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $taskVsRoot) { throw 'MSVC x64 tools unavailable.' }
    $taskBuild = '.cache/m3c-build/' + [guid]::NewGuid().ToString('N')
    New-Item -ItemType Directory -Force -Path $taskBuild | Out-Null
    $taskWin = $taskBuild.Replace('/', '\')
    $taskVcvars = Join-Path $taskVsRoot 'VC/Auxiliary/Build/vcvars64.bat'
    $taskExports = [regex]::Matches((Get-Content -Raw 'include/ct_cuda.h'), ' X\((cu\w+),') | ForEach-Object { '    ' + $_.Groups[1].Value }
    @('LIBRARY nvcuda.dll', 'EXPORTS') + $taskExports | Set-Content -Encoding ascii (Join-Path $taskBuild 'nvcuda.def')
    @('@echo off', ('call "' + $taskVcvars + '" >nul'), 'if errorlevel 1 exit /b 1',
      ('lib /nologo /def:' + $taskWin + '\nvcuda.def /machine:x64 /out:' + $taskWin + '\nvcuda.lib'),
      'if errorlevel 1 exit /b 1',
      ('cl /nologo /O2 /MD /EHsc /std:c++17 /utf-8 /I.cache\reference\cuda-12.0\include /I.cache\vendor\cuda-samples-12.0\Common .cache\vendor\cuda-samples-12.0\Samples\0_Introduction\vectorAddDrv\vectorAddDrv.cpp ' + $taskWin + '\nvcuda.lib /Fo' + $taskWin + '\vectorAddDrv.obj /Fe' + $taskWin + '\vectorAddDrv.exe')
    ) | Set-Content -Encoding utf8NoBOM (Join-Path $taskBuild 'build.cmd')
    & cmd.exe /d /c ($taskWin + '\build.cmd')
    if ($LASTEXITCODE -ne 0) { throw 'Unchanged official CUDA host build failed.' }
    if ($AlternativeFatbin) { & python tests/m3d_fatbin_check.py $taskBuild --alternatives }
    elseif ($CompressedFatbin) { & python tests/m3d_fatbin_check.py $taskBuild --compressed }
    elseif ($BinaryFatbin) { & python tests/m3d_fatbin_check.py $taskBuild }
    else { & python tests/m3c_external_check.py run $taskBuild }
    if ($LASTEXITCODE -ne 0) { throw 'Official sample connection verification failed.' }
} finally { Pop-Location }
