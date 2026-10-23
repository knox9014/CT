param([string]$ProducerManifest='.cache/p09a2-producer/manifest.json')
$ErrorActionPreference='Stop'
$ctRepo=Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $ctRepo
try {
    Remove-Item -LiteralPath '.cache/p09a2c-abi-latest.json' -ErrorAction SilentlyContinue
    & python scripts/prepare_nvcc_probe.py replay --manifest $ProducerManifest
    if ($LASTEXITCODE -ne 0) {throw 'Producer inputs invalid.'}
    $ctProducer=Get-Content -LiteralPath $ProducerManifest -Raw | ConvertFrom-Json
    if ($ctProducer.host.profile -ne 'diagnostic') {throw 'This gate requires explicit diagnostic producer profile.'}
    $ctBuild=Join-Path $ctRepo ('.cache/p09a2c-build/'+[guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $ctBuild -Force | Out-Null
    $ctProducerRoot=Split-Path -Parent ([IO.Path]::GetFullPath((Join-Path $ctRepo $ProducerManifest)))
    $ctCompiler=Split-Path -Parent $ctProducer.host.tools.'cl.exe'.path
    $ctVsWhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $ctVsRoot=& $ctVsWhere -latest -products '*' -property installationPath
    $ctVcvars=Join-Path $ctVsRoot 'VC/Auxiliary/Build/vcvars64.bat'
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $ctVcvars).Hash.ToLowerInvariant() -ne $ctProducer.host.vcvars.sha256) {throw 'Installed host differs from producer.'}
    $ctCommands=@('@echo off',('call "'+$ctVcvars+'" >nul'),'if errorlevel 1 exit /b 1')
    foreach($ctKey in @('NVCC_PREPEND_FLAGS','NVCC_APPEND_FLAGS','NVCC_CCBIN','CL','_CL_','LINK','_LINK_','CUDAHOSTCXX','CUDACXX','CPATH','CPLUS_INCLUDE_PATH','C_INCLUDE_PATH','CPPFLAGS','CFLAGS','CXXFLAGS','LDFLAGS','COMPILER_PATH','GCC_EXEC_PREFIX','LIBRARY_PATH')) {$ctCommands+=('set "'+$ctKey+'="')}
    $ctCommands+=('set "PATH='+$ctCompiler+';%PATH%"')
    foreach($ctSource in @('runtime_default_reference_abi','runtime_default_declared_abi','runtime_default_native_abi')) {
        $ctCommands+=('"'+$ctCompiler+'/cl.exe" /nologo /W4 /WX /EHsc /Gy /std:c++17 /utf-8 /external:W0 /external:I"'+$ctProducerRoot+'/toolkit/include" tests/'+$ctSource+'.cpp /Fo"'+$ctBuild+'/'+$ctSource+'.obj" /Fe"'+$ctBuild+'/'+$ctSource+'.exe" /link /OPT:REF')
        $ctCommands+='if errorlevel 1 exit /b 1'
    }
    foreach($ctItem in @(@('ct_foreign','p09a2_foreign_kernel_driver.c',''),@('missing','p09a2_missing_kernel_driver.c',''),@('forwarded','p09a2_missing_kernel_driver.c',(' "'+$ctBuild+'/ct_foreign.lib" /link /def:tests/p09a2_forwarded_kernel.def')))) {
        $ctCommands+=('"'+$ctCompiler+'/cl.exe" /nologo /W4 /WX /LD tests/'+$ctItem[1]+' /Fo"'+$ctBuild+'/'+$ctItem[0]+'.obj" /Fe"'+$ctBuild+'/'+$ctItem[0]+'.dll"'+$ctItem[2])
        $ctCommands+='if errorlevel 1 exit /b 1'
    }
    $ctCommands | Set-Content -Encoding utf8NoBOM -LiteralPath "$ctBuild/build.cmd"
    & cmd.exe /d /c ('"'+$ctBuild+'\build.cmd"') *> "$ctBuild/compile.log"
    if($LASTEXITCODE -ne 0){throw 'Kernel ABI compilation failed; local compile.log retained.'}
    $ctPreviousTarget=$env:CARGO_TARGET_DIR;$ctPreviousIncremental=$env:CARGO_INCREMENTAL
    try {
        $env:CARGO_TARGET_DIR=Join-Path $ctBuild 'runtime-target';$env:CARGO_INCREMENTAL='0'
        & cargo build --manifest-path crates/ct-cudart/Cargo.toml --locked
        if($LASTEXITCODE -ne 0){throw 'Runtime build failed.'}
        Copy-Item -LiteralPath "$ctBuild/runtime-target/debug/ct_cudart.dll" -Destination "$ctBuild/ct_cudart.dll"
    } finally {$env:CARGO_TARGET_DIR=$ctPreviousTarget;$env:CARGO_INCREMENTAL=$ctPreviousIncremental}
    & python scripts/runtime_default_abi_evidence.py $ctBuild --producer $ProducerManifest
    if($LASTEXITCODE -ne 0){throw 'Kernel ABI evidence failed.'}
} finally {Pop-Location}
