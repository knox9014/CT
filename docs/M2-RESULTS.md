# M2: PTX to Intel GPU execution

Validated on 2026-10-19, Windows x64, Intel Arc B390, display driver 32.0.101.8622, Level Zero loader v1.27.0 / driver API 1.14. Results apply to this environment and the restricted [PTX profile](compatibility/ptx-profile.md).

An independent C host loads `ct_cuda.dll`, supplies synthetic PTX to `cuModuleLoadData`, obtains the entry through `cuModuleGetFunction`, and calls `cuLaunchKernel`. CT parses PTX, emits SPIR-V, compiles through Level Zero and executes on the GPU. Outputs are copied back and checked against independent CPU references. There is no CPU execution fallback.

| Check | Observed result |
| --- | --- |
| Vector add, SAXPY, ReLU, matrix multiply | 4 kernels, 53 cases passed |
| Output verification | 606,660 output values and 4,992 guard values passed |
| Independent C host | 613,056 checks passed, including error/handle contracts |
| M1 regression | 210 checks, 2 threads, 32 context cycles passed |
| M0 regression | Real GPU test passed, 16 dispatch/boundary combinations |
| Rust workspace | 13 tests passed, including explicitly enabled GPU test |
| Native ABI oracle | 12 structures matched pinned official C header layouts |
| Publication guard | 6 tests passed |
| Static checks | Formatting and clippy with warnings denied passed |

Elementwise lengths: 1, 63, 64, 65, 255, 256, 257, 100003, each with group sizes 64 and 128. Matrix widths: 3, 8, 17, with explicit loops and separate multiply/add. Additional variants rename the entry and change addition to subtraction, and change a ReLU floating constant. Outputs start as NaNs and include guards to expose missing writes and overdispatch writes.

Negative checks cover malformed/unsupported PTX, unsupported launch dimensions/options, null pointer arguments, missing entries, foreign contexts and stale handles. Parser tests cover types/modifiers, reserved names, assignment on every branch, loop initialization and octal constants/offsets. Independent review found octal literals interpreted as decimal; a failing regression reproduced it before correction, and the reviewer confirmed the fix.

## Reproduce

Requires Rust MSVC x64, MSVC C++ tools, Python and an Intel GPU with a working Level Zero driver. The ABI script requires the official v1.27.0 `ze_api.h` at `.cache/reference/ze_api.h`, checked by SHA-256. See [M0 setup](M0-RESULTS.md).

```powershell
$env:CARGO_INCREMENTAL = '0'
cargo fmt --all -- --check
cargo test --workspace -- --include-ignored
cargo clippy --workspace --all-targets -- -D warnings
./scripts/run_m2_smoke.ps1
./scripts/run_m1_smoke.ps1
./scripts/check_level_zero_abi.ps1
python -m unittest discover -s tests -p test_public_artifacts.py -v
python scripts/check_public_artifacts.py --tracked --identity
```

Build products, raw local logs, temporary reference files and compiled modules stay in ignored local directories. Published fixtures are synthetic PTX. No local user documents, credentials or raw diagnostic dumps are included.

## Limits

M2 adds four exports, 24 total. Existing unmodified CUDA applications, CUDA Runtime, PyTorch CUDA, CUDA libraries and AMD remain unsupported. There is no system `nvcuda.dll` replacement installation. Callers must provide trusted terminating kernels with valid memory extents.

The native driver compiled and executed emitted SPIR-V. Official `spirv-val` was unavailable and was not run. NVIDIA GPU/SDK comparison, full PTX floating-point conformance, fault recovery, performance parity and broad device portability remain unverified. No performance claim is made.
