param([string]$BaselineDll = '')
$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    & cargo build -p ct-cuda
    if ($LASTEXITCODE -ne 0) { throw 'CT build failed.' }
    $taskHeaders = (Resolve-Path -LiteralPath '.cache/reference/cuda-12.0/include').Path
    & python scripts/check_toolchain_files.py cuda-headers $taskHeaders
    if ($LASTEXITCODE -ne 0) { throw 'Header pin mismatch.' }
    $taskVsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $taskVsRoot = & $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $taskVsRoot) { throw 'MSVC unavailable.' }
    $taskBuild = '.cache/p06a-build/' + [guid]::NewGuid().ToString('N')
    New-Item -ItemType Directory -Force -Path $taskBuild | Out-Null
    $taskBuildWin = $taskBuild.Replace('/', '\')
    @('@echo off', ('call "' + (Join-Path $taskVsRoot 'VC/Auxiliary/Build/vcvars64.bat') + '" >nul'), 'if errorlevel 1 exit /b 1',
      ('cl /nologo /W4 /WX /utf-8 /external:W0 /external:I"' + $taskHeaders + '" tests\p06a_memory_app.c /Fo' + $taskBuildWin + '\host.obj /Fe' + $taskBuildWin + '\host.exe')
    ) | Set-Content -Encoding utf8NoBOM (Join-Path $taskBuild 'build.cmd')
    & cmd.exe /d /c ($taskBuildWin + '\build.cmd')
    if ($LASTEXITCODE -ne 0) { throw 'Memory consumer build failed.' }
    $taskArguments = @('tests/p06a_memory_check.py', $taskBuild)
    if ($BaselineDll) { $taskArguments += @('--baseline-dll', $BaselineDll) }
    & python @taskArguments
    if ($LASTEXITCODE -ne 0) { throw 'Device memory verification failed.' }
} finally { Pop-Location }
