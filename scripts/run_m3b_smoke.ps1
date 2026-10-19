param([switch]$SkipCtBuild)
$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    $taskHeaderHashes = @{
        'cuda.h' = 'AA801E582DC7CC251BB7D7D84EEBCE0A852F4162F272DC40AE33C21CC2A0AFBA'
        'cudaTypedefs.h' = 'D0691E868DEA2108237A899E2C1E9685CC7BD4D7D68F63B0C6B3DF2A7CEB4774'
    }
    foreach ($taskName in $taskHeaderHashes.Keys) {
        if ((Get-FileHash -LiteralPath (Join-Path '.cache/reference' $taskName) -Algorithm SHA256).Hash -ne $taskHeaderHashes[$taskName]) {
            throw 'Expected pinned NVIDIA 12.0.107 headers; see M3b results.'
        }
    }
    if (-not $SkipCtBuild) {
        & cargo build -p ct-cuda
        if ($LASTEXITCODE -ne 0) { throw 'CT DLL build failed.' }
    }
    $taskVsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $taskVsRoot = & $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $taskVsRoot) { throw 'MSVC x64 tools unavailable.' }
    $taskVcvars = Join-Path $taskVsRoot 'VC/Auxiliary/Build/vcvars64.bat'
    $taskBuild = '.cache/m3b-build/' + [guid]::NewGuid().ToString('N')
    New-Item -ItemType Directory -Force -Path $taskBuild | Out-Null
    $taskBuildWin = $taskBuild.Replace('/', '\')
    @('@echo off', ('call "' + $taskVcvars + '" >nul'), 'if errorlevel 1 exit /b 1',
      ('cl /nologo /W4 /WX /utf-8 /external:I.cache\reference /external:W0 tests\m3b_cuda_app.c /Fo' + $taskBuildWin + '\m3b_cuda.obj /Fe' + $taskBuildWin + '\m3b_cuda.exe')
    ) | Set-Content -Encoding utf8NoBOM (Join-Path $taskBuild 'build.cmd')
    & cmd.exe /d /c ($taskBuildWin + '\build.cmd')
    if ($LASTEXITCODE -ne 0) { throw 'NVIDIA-header consumer build failed.' }
    & python tests/m3b_connection_check.py $taskBuild
    if ($LASTEXITCODE -ne 0) { throw 'M3b versioned CUDA connection failed.' }
} finally {
    Pop-Location
}
