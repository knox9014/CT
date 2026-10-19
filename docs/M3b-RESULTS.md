# M3b: versioned CUDA Driver entry-point connection

Validated 2026-10-19 on Windows x64 / Intel Arc B390, using the M2/M3a environment. CT now exports the four-argument `cuGetProcAddress` and five-argument `cuGetProcAddress_v2`, bringing the experimental total to 26. See the [exact lookup policy](compatibility/driver-entrypoints.md).

## What ran

An independent C application includes only NVIDIA's official `cuda.h` and `cudaTypedefs.h`, not CT headers. It dynamically opens `nvcuda.dll`, obtains either resolver and queries canonical CUDA base names with versioned NVIDIA function-pointer typedefs. It compares all 24 previously implemented function addresses with direct exports, checks resolver self-selection and incompatible ABI rejection, then allocates memory, loads PTX and launches vector addition entirely through returned function pointers.

The same executable runs once through each resolver. Application and external PTX bytes are preserved by the existing process-local launcher; original files and system drivers are unchanged. Only headers were extracted from the official runtime distribution; NVIDIA runtime binaries were neither installed nor loaded.

| Check | Result |
| --- | --- |
| Official-header consumer | Both resolver modes passed; 80 queries in total |
| Real GPU outputs | 514 values and 128 guards passed |
| Rust workspace | 16 tests passed, including 3 resolver tests and the M0 GPU test |
| Python loader/publication suites | All 13 tests passed |
| M3a static/dynamic ordinary loading | Both modes passed; 514 values and 128 guards |
| M2 restricted PTX | 53 cases / 613,056 checks passed |
| M1 memory/context | 210 checks passed |
| Native Level Zero C ABI oracle | All 12 structure layouts matched |
| Formatting/clippy | Passed with warnings denied |

Resolver tests exercise every canonical entry's lower ABI boundary, context-create signature transition, output clearing, missing symbols, explicit version suffix rejection, flags, null arguments, lookup without initialization, nested resolver calls and concurrent lookup. The independent C application is compiled with MSVC warnings as errors; warnings in pinned vendor headers are excluded through MSVC external-header handling.

Test-first evidence: Rust resolver imports failed before implementation. The C consumer compiled against the official headers but returned exit 42 (missing resolver exports) with the prior M3a DLL; it passed after building the M3b DLL. Independent review checked version floors and contracts and independently reran all three resolver tests without actionable findings.

## Reproduce

Requirements: Windows x64, Python, Rust MSVC, MSVC C++ tools and a working Intel Level Zero device. Acquire the pinned [NVIDIA runtime distribution](https://pypi.org/project/nvidia-cuda-runtime-cu12/12.0.107/) without installation:

```powershell
python -m pip download --no-deps --dest .cache/reference nvidia-cuda-runtime-cu12==12.0.107
@'
import hashlib, pathlib, zipfile
root = pathlib.Path('.cache/reference')
wheel = root / 'nvidia_cuda_runtime_cu12-12.0.107-py3-none-win_amd64.whl'
assert hashlib.sha256(wheel.read_bytes()).hexdigest() == 'f595d66142e9ba5d1157d73ef06488735d814415a462714426f3989344e675eb'
with zipfile.ZipFile(wheel) as archive:
    for name in ('cuda.h', 'cudaTypedefs.h'):
        matches = [n for n in archive.namelist() if n.endswith('/include/' + name)]
        assert len(matches) == 1
        (root / name).write_bytes(archive.read(matches[0]))
'@ | python -
$env:CARGO_INCREMENTAL = '0'
./scripts/run_m3b_smoke.ps1
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py' -v
```

The smoke script verifies both extracted header SHA-256 values before compiling. The wheel, headers, binaries, bundles and raw local logs stay ignored. No NVIDIA headers or runtime binaries are committed. `-SkipCtBuild` uses the existing DLL and is intended only for development regression checks.

## Remaining gaps

This is an official-header-compiled synthetic consumer, not an external application's compatibility result, nvcc validation or a comparison with NVIDIA hardware. The implementation has a lookup ceiling of 12000, supports only default/legacy flags and rejects newer context-create signatures; it does not claim CUDA 12 conformance. `cuDriverGetVersion` still reports NOT_SUPPORTED with output zero. Programs requiring a successful version probe remain unsupported.

All original PTX limitations remain. CUDA Runtime/cudart, per-thread stream behavior, broad application dependencies, external unmodified applications, NVIDIA coexistence/original execution and AMD remain unverified or unimplemented. No performance or full M3/v0.1 claim is made. The next application-facing work is dependency/version-probe diagnosis and a concrete external program whose requirements can be checked against CT's actual support.
