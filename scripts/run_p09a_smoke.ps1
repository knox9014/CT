param()
$ErrorActionPreference='Stop'
$taskRepo=Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    $taskBuild='.cache/p09a-build/'+[guid]::NewGuid().ToString('N')
    & "$PSScriptRoot/check_runtime_abi.ps1" -BuildDirectory $taskBuild
    & cargo build -p ct-cuda --locked
    if($LASTEXITCODE -ne 0){throw 'Driver build failed.'}
    $taskVsWhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $taskVsRoot=& $taskVsWhere -latest -products '*' -property installationPath
    $taskAbsolute=Join-Path $taskRepo $taskBuild
    $taskCommands=@('@echo off',('call "'+(Join-Path $taskVsRoot 'VC/Auxiliary/Build/vcvars64.bat')+'" >nul'), 'if errorlevel 1 exit /b 1',
        ('lib /nologo /machine:x64 /def:tests/p09a_runtime.def /out:"'+$taskAbsolute+'/cudart.lib"'),'if errorlevel 1 exit /b 1',
        ('cl /nologo /W4 /WX /utf-8 /external:W0 /external:I"'+$taskAbsolute+'/headers/runtime" /external:I"'+$taskAbsolute+'/headers/support" /sourceDependencies "'+$taskAbsolute+'/consumer-deps.json" tests/p09a_runtime_app.c "'+$taskAbsolute+'/cudart.lib" /Fo"'+$taskAbsolute+'/host.obj" /Fe"'+$taskAbsolute+'/host.exe"'),'if errorlevel 1 exit /b 1',
        ('cl /nologo /W4 /WX /LD tests/p09a_fake_driver.c /Fo"'+$taskAbsolute+'/fake.obj" /Fe"'+$taskAbsolute+'/fake.dll"'),'if errorlevel 1 exit /b 1')
    foreach($taskControl in @('COPY','FILL')) {
        $taskName='noop_'+$taskControl.ToLowerInvariant()
        $taskCommands+=('cl /nologo /W4 /WX /LD /DNOOP_'+$taskControl+' tests/p09a_noop_driver.c /Fo"'+$taskAbsolute+'/'+$taskName+'.obj" /Fe"'+$taskAbsolute+'/'+$taskName+'.dll" /link /def:tests/p09a_driver_control.def')
        $taskCommands+='if errorlevel 1 exit /b 1'
    }
    $taskCommands | Set-Content -Encoding utf8NoBOM "$taskAbsolute/native.cmd"
    & cmd.exe /d /c ('"'+$taskAbsolute+'\native.cmd"')
    if($LASTEXITCODE -ne 0){throw 'Runtime native fixture build failed.'}
    & python scripts/check_runtime_header_closure.py "$taskAbsolute/consumer-deps.json" "$taskAbsolute/headers"
    if($LASTEXITCODE -ne 0){throw 'Consumer header closure mismatch.'}
    & python tests/p09a_runtime_check.py $taskBuild
    if($LASTEXITCODE -ne 0){throw 'Runtime native verification failed.'}
} finally {Pop-Location}
