param([string]$HeaderDirectory = '.cache/reference')
$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRepo
try {
    $taskHeaderRoot = (Resolve-Path -LiteralPath $HeaderDirectory).Path
    $taskHeader = Join-Path $taskHeaderRoot 'ze_api.h'
    $taskExpectedHash = '3E7967D37CE79A472205C9CC230DA837173BA390686BC4017E980E1290E40FEB'
    if ((Get-FileHash -LiteralPath $taskHeader -Algorithm SHA256).Hash -ne $taskExpectedHash) {
        throw 'Expected the official oneapi-src/level-zero v1.27.0 ze_api.h (see M0 evidence document).'
    }
    $taskVsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $taskVsRoot = & $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $taskVsRoot) { throw 'MSVC x64 C++ tools not found.' }
    $taskVcvars = Join-Path $taskVsRoot 'VC/Auxiliary/Build/vcvars64.bat'
    New-Item -ItemType Directory -Force -Path '.cache/reference' | Out-Null
    # Use a batch file to preserve paths with spaces across the PowerShell/cmd boundary.
    @('@echo off', 'chcp 65001 >nul', ('call "' + $taskVcvars + '" >nul'),
        'if errorlevel 1 exit /b 1',
        ('cl /nologo /W4 /I"' + $taskHeaderRoot + '" tests\abi_layout.c /Fo.cache\reference\abi_layout.obj /Fe.cache\reference\abi_layout.exe')
    ) | Set-Content -Encoding utf8NoBOM '.cache/reference/check-abi.cmd'
    cmd.exe /d /c .cache\reference\check-abi.cmd
    if ($LASTEXITCODE -ne 0) { throw 'C ABI probe compilation failed.' }
    $taskCLayout = & '.\.cache\reference\abi_layout.exe'
    if ($LASTEXITCODE -ne 0) { throw 'C ABI probe failed.' }
    $taskRustLayout = & cargo run --quiet --bin ct-abi-layout
    if ($LASTEXITCODE -ne 0) { throw 'Rust ABI probe failed.' }
    $taskCLayout | Set-Content -Encoding utf8 '.cache/reference/c-layout.txt'
    $taskRustLayout | Set-Content -Encoding utf8 '.cache/reference/rust-layout.txt'
    $taskDiff = Compare-Object $taskCLayout $taskRustLayout
    if ($taskDiff) { $taskDiff | Out-String | Write-Error; throw 'C/Rust ABI mismatch.' }
    Write-Output ('ABI match: {0} structures, every field offset, size and alignment.' -f $taskCLayout.Count)
} finally {
    Pop-Location
}
