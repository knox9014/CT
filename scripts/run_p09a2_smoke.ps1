param([ValidateSet('diagnostic','qualified')][string]$HostProfile='diagnostic',[string]$ProducerManifest='.cache/p09a2-producer/manifest.json')
$ErrorActionPreference='Stop'
$ctRepo=Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $ctRepo
try {
    Remove-Item -LiteralPath '.cache/p09a2-kernel-latest.json' -ErrorAction SilentlyContinue
    & python scripts/prepare_nvcc_probe.py replay --manifest $ProducerManifest
    if($LASTEXITCODE -ne 0){throw 'Producer validation failed.'}
    $ctProducer=Get-Content -LiteralPath $ProducerManifest -Raw | ConvertFrom-Json
    if($HostProfile -ne 'diagnostic' -or $ctProducer.host.profile -ne $HostProfile){throw 'Supported-host qualification is unavailable; diagnostic evidence cannot qualify it.'}
    & python -c "import sys,json;from pathlib import Path;sys.path.insert(0,'scripts');from runtime_kernel_abi_evidence import audit;p=Path('.cache/p09a2-abi-latest.json');v=json.loads(p.read_bytes()) if p.is_file() else {};sys.exit(bool(audit(v.get('manifest','missing'))))"
    if($LASTEXITCODE -ne 0){& "$PSScriptRoot/check_runtime_kernel_abi.ps1" -ProducerManifest $ProducerManifest;if($LASTEXITCODE -ne 0){throw 'Kernel ABI prerequisite failed.'}}
    $ctAbiPointer=Get-Content -LiteralPath '.cache/p09a2-abi-latest.json' -Raw | ConvertFrom-Json
    $ctAbi=Get-Content -LiteralPath $ctAbiPointer.manifest -Raw | ConvertFrom-Json
    $ctBuild=Join-Path $ctRepo ('.cache/p09a2-kernel/'+[guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path "$ctBuild/keep" | Out-Null
    foreach($ctSource in @('kernel_oracle.cu','module_a.cu','module_b.cu')) {Copy-Item -LiteralPath "tests/fixtures/p09a2/$ctSource" -Destination "$ctBuild/$ctSource"}
    Copy-Item -LiteralPath 'include/ct_cuda.h' -Destination "$ctBuild/ct_cuda.h"
    $ctProducerRoot=Split-Path -Parent ([IO.Path]::GetFullPath((Join-Path $ctRepo $ProducerManifest)))
    $ctCompiler=Split-Path -Parent $ctProducer.host.tools.'cl.exe'.path
    $ctVsWhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $ctVsRoot=& $ctVsWhere -latest -products '*' -property installationPath
    $ctVcvars=Join-Path $ctVsRoot 'VC/Auxiliary/Build/vcvars64.bat'
    if((Get-FileHash -Algorithm SHA256 -LiteralPath $ctVcvars).Hash.ToLowerInvariant() -ne $ctProducer.host.vcvars.sha256){throw 'Installed host differs from producer.'}
    $ctCommands=@('@echo off',('call "'+$ctVcvars+'" >nul'),'if errorlevel 1 exit /b 1')
    $ctBlocked=@('NVCC_PREPEND_FLAGS','NVCC_APPEND_FLAGS','NVCC_CCBIN','CL','_CL_','LINK','_LINK_','CUDAHOSTCXX','CUDACXX','CPATH','CPLUS_INCLUDE_PATH','C_INCLUDE_PATH','OBJC_INCLUDE_PATH','CPPFLAGS','CFLAGS','CXXFLAGS','LDFLAGS','COMPILER_PATH','GCC_EXEC_PREFIX','LIBRARY_PATH')
    $ctBlocked+=@(Get-ChildItem Env: | Where-Object {$_.Name -like 'NVCC_*'} | ForEach-Object {$_.Name})
    foreach($ctKey in $ctBlocked | Select-Object -Unique){$ctCommands+=('set "'+$ctKey+'="')}
    $ctCommands+=('set "PATH='+$ctCompiler+';%PATH%"')
    $ctCommands+='pushd "%~dp0"'
    $ctCommands+=('"'+$ctProducerRoot+'/toolkit/bin/nvcc.exe" --std=c++17 --compiler-bindir "'+$ctCompiler+'" -allow-unsupported-compiler -I "'+$ctProducerRoot+'/stl" -Xcompiler /utf-8 --cudart=shared --cudadevrt=none --keep --keep-dir keep --generate-code arch=compute_52,code=compute_52 kernel_oracle.cu module_a.cu module_b.cu -o host.exe')
    $ctCommands+='if errorlevel 1 exit /b 1';$ctCommands+='popd'
    $ctCommands+=('"'+$ctCompiler+'/cl.exe" /nologo /W4 /WX /EHsc /std:c++17 /utf-8 tests/p09a2_kernel_control.cpp /Fo"'+$ctBuild+'/control.obj" /Fe"'+$ctBuild+'/control.exe"')
    $ctCommands+='if errorlevel 1 exit /b 1'
    $ctCommands+=('"'+$ctCompiler+'/cl.exe" /nologo /W4 /WX /LD /DNOOP_LAUNCH tests/p09a_noop_driver.c /Fo"'+$ctBuild+'/noop.obj" /Fe"'+$ctBuild+'/noop.dll" /link /def:tests/p09a_driver_control.def')
    $ctCommands+='if errorlevel 1 exit /b 1'
    $ctCommands | Set-Content -Encoding utf8NoBOM -LiteralPath "$ctBuild/build.cmd"
    & cmd.exe /d /c ('"'+$ctBuild+'\build.cmd"') *> "$ctBuild/compile.log"
    if($LASTEXITCODE -ne 0){throw 'nvcc kernel fixture compilation failed; local compile.log retained.'}
    Copy-Item -LiteralPath "$ctBuild/keep/kernel_oracle.fatbin" -Destination "$ctBuild/kernel_oracle.fatbin"
    $ctPreviousTarget=$env:CARGO_TARGET_DIR;$ctPreviousIncremental=$env:CARGO_INCREMENTAL
    try {
        $env:CARGO_TARGET_DIR=Join-Path $ctBuild 'driver-target';$env:CARGO_INCREMENTAL='0'
        & cargo build -p ct-cuda --locked
        if($LASTEXITCODE -ne 0){throw 'CT Driver build failed.'}
        Copy-Item -LiteralPath "$ctBuild/driver-target/debug/ct_cuda.dll" -Destination "$ctBuild/ct_cuda.dll"
    } finally {$env:CARGO_TARGET_DIR=$ctPreviousTarget;$env:CARGO_INCREMENTAL=$ctPreviousIncremental}
    Copy-Item -LiteralPath $ctAbi.artifacts.runtime.path -Destination "$ctBuild/ct_cudart.dll"
    & python tests/p09a2_kernel_check.py $ctBuild --producer $ProducerManifest
    if($LASTEXITCODE -ne 0){throw 'Actual Runtime kernel oracle failed.'}
} finally {Pop-Location}
