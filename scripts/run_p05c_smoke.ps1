param([string]$BaselineDll = '')
$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    & cargo build -p ct-cuda
    if ($LASTEXITCODE -ne 0) { throw 'CT build failed.' }
    $taskHeaders = (Resolve-Path -LiteralPath '.cache/reference/cuda-12.0/include').Path
    & python scripts/check_toolchain_files.py cuda-headers $taskHeaders
    if ($LASTEXITCODE -ne 0) { throw 'Official header pin mismatch.' }
    $taskVsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $taskVsRoot = & $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $taskVsRoot) { throw 'MSVC tools unavailable.' }
    $taskVcvars = Join-Path $taskVsRoot 'VC/Auxiliary/Build/vcvars64.bat'
    $taskBuild = '.cache/p05c-build/' + [guid]::NewGuid().ToString('N')
    New-Item -ItemType Directory -Force -Path $taskBuild | Out-Null
    $taskBuildWin = $taskBuild.Replace('/', '\')
    $taskExports = [regex]::Matches((Get-Content -Raw 'include/ct_cuda.h'), ' X\((cu\w+),') | ForEach-Object { '    ' + $_.Groups[1].Value }
    @('LIBRARY nvcuda.dll', 'EXPORTS') + $taskExports | Set-Content -Encoding ascii (Join-Path $taskBuild 'nvcuda.def')
    $taskCommands = @('@echo off', ('call "' + $taskVcvars + '" >nul'), 'if errorlevel 1 exit /b 1',
      ('lib /nologo /def:' + $taskBuildWin + '\nvcuda.def /machine:x64 /out:' + $taskBuildWin + '\nvcuda.lib'), 'if errorlevel 1 exit /b 1')
    foreach ($taskRole in @('producer','consumer','host')) {
        $taskShared = if ($taskRole -eq 'host') { '' } else { '/LD ' }
        $taskLink = if ($taskRole -eq 'producer') { $taskBuildWin + '\nvcuda.lib ' } else { '' }
        $taskExtension = if ($taskRole -eq 'host') { '.exe' } else { '.dll' }
        $taskCommands += ('cl /nologo /W4 /WX /utf-8 /external:W0 ' + $taskShared + '/external:I"' + $taskHeaders + '" tests\p05c_' + $taskRole + '.c ' + $taskLink + '/Fo' + $taskBuildWin + '\' + $taskRole + '.obj /Fe' + $taskBuildWin + '\' + $taskRole + $taskExtension + ' /link /IMPLIB:' + $taskBuildWin + '\' + $taskRole + '.lib')
        $taskCommands += 'if errorlevel 1 exit /b 1'
    }
    $taskCommands += ('cl /nologo /W4 /WX /utf-8 /external:W0 /LD /DCT_TEST_SKIP_SECOND_LAUNCH /external:I"' + $taskHeaders + '" tests\p05c_consumer.c /Fo' + $taskBuildWin + '\consumer-noop.obj /Fe' + $taskBuildWin + '\consumer-noop.dll /link /IMPLIB:' + $taskBuildWin + '\consumer-noop.lib')
    $taskCommands += 'if errorlevel 1 exit /b 1'
    $taskCommands | Set-Content -Encoding utf8NoBOM (Join-Path $taskBuild 'build.cmd')
    & cmd.exe /d /c ($taskBuildWin + '\build.cmd')
    if ($LASTEXITCODE -ne 0) { throw 'Independent libraries/host build failed.' }
    $taskArguments = @('tests/p05c_libraries_check.py', $taskBuild)
    if ($BaselineDll) { $taskArguments += @('--baseline-dll', $BaselineDll) }
    & python @taskArguments
    if ($LASTEXITCODE -ne 0) { throw 'Library consumer verification failed.' }
} finally { Pop-Location }
