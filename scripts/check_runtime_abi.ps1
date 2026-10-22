param([string]$BuildDirectory = '')
$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    if (-not $BuildDirectory) { $BuildDirectory = '.cache/p09a-build/' + [guid]::NewGuid().ToString('N') }
    $taskBuild = [IO.Path]::GetFullPath((Join-Path $taskRepo $BuildDirectory))
    $taskAllowed = [IO.Path]::GetFullPath((Join-Path $taskRepo '.cache/p09a-build')) + [IO.Path]::DirectorySeparatorChar
    if (-not $taskBuild.StartsWith($taskAllowed,[StringComparison]::OrdinalIgnoreCase)) { throw 'Build directory outside local root.' }
    New-Item -ItemType Directory -Force -Path $taskBuild | Out-Null
    & python scripts/prepare_runtime_headers.py "$taskBuild/headers"
    if ($LASTEXITCODE -ne 0) { throw 'Runtime header preparation failed.' }
    foreach ($taskPin in @(@('cuda-runtime-headers','runtime'),@('cuda-nvcc-support-headers','support'))) {
        & python scripts/check_toolchain_files.py $taskPin[0] "$taskBuild/headers/$($taskPin[1])"
        if ($LASTEXITCODE -ne 0) { throw 'Runtime header pin mismatch.' }
    }
    $taskVsWhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $taskVsRoot=& $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $taskVsRoot) {throw 'MSVC unavailable.'}
    $taskCommands=@('@echo off',('call "'+(Join-Path $taskVsRoot 'VC/Auxiliary/Build/vcvars64.bat')+'" >nul'),'if errorlevel 1 exit /b 1')
    foreach($taskProbe in @('runtime_reference_abi','runtime_declared_abi')) {
        $taskCommands+=('cl /nologo /W4 /WX /EHsc /std:c++17 /utf-8 /external:W0 /external:I"'+$taskBuild+'/headers/runtime" /external:I"'+$taskBuild+'/headers/support" /sourceDependencies "'+$taskBuild+'/'+$taskProbe+'-deps.json" tests/'+$taskProbe+'.cpp /Fo"'+$taskBuild+'/'+$taskProbe+'.obj" /Fe"'+$taskBuild+'/'+$taskProbe+'.exe"')
        $taskCommands+='if errorlevel 1 exit /b 1'
    }
    $taskCommands | Set-Content -Encoding utf8NoBOM "$taskBuild/abi.cmd"
    & cmd.exe /d /c ('"'+$taskBuild+'\abi.cmd"')
    if ($LASTEXITCODE -ne 0) {throw 'Runtime ABI compilation failed.'}
    $taskReference=& "$taskBuild/runtime_reference_abi.exe"
    $taskDeclared=& "$taskBuild/runtime_declared_abi.exe"
    if ($LASTEXITCODE -ne 0 -or (Compare-Object $taskReference $taskDeclared -SyncWindow 0)) {throw 'Runtime ABI mismatch.'}
    & python scripts/check_runtime_header_closure.py "$taskBuild/runtime_reference_abi-deps.json" "$taskBuild/headers"
    if ($LASTEXITCODE -ne 0) {throw 'Runtime include closure mismatch.'}
    & python scripts/runtime_abi_evidence.py $taskBuild
    if ($LASTEXITCODE -ne 0) {throw 'Runtime ABI artifact audit failed.'}
    $taskPreviousTarget=$env:CARGO_TARGET_DIR
    $taskPreviousIncremental=$env:CARGO_INCREMENTAL
    try {
        $env:CARGO_TARGET_DIR=Join-Path $taskBuild 'runtime-target'
        $env:CARGO_INCREMENTAL='0'
        & cargo build --manifest-path crates/ct-cudart/Cargo.toml --locked
        if ($LASTEXITCODE -ne 0) {throw 'Runtime DLL build failed.'}
    } finally {$env:CARGO_TARGET_DIR=$taskPreviousTarget;$env:CARGO_INCREMENTAL=$taskPreviousIncremental}
    Write-Output 'Runtime ABI: 14 signatures and fixed enum values passed; native execution is separate.'
} finally {Pop-Location}
