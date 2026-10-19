# M1: experimental CUDA Driver memory ABI

Date: 2026-10-19. Environment: the Windows x64 / Intel Arc B390 setup recorded in `environment-matrix.md`.

## Implemented

CT now builds `ct_cuda.dll` and exports the narrow 20-symbol subset listed in `compatibility/driver-api.md`. An independent MSVC C executable loads this DLL by explicit absolute path and calls CUDA-style initialization, device queries, per-thread context operations, native device-memory allocation/free, synchronous HtoD/DtoH and error lookup.

The backend uses installed Level Zero APIs, genuine device allocations and pinned staging. It is not a CPU-backed substitute for device allocations. Driver implementation details of small transfers are not profiled; no assertion about physical copy-engine use is made.

## Observed verification

| Check | Result |
| --- | --- |
| Independent C ABI host | 210 checks passed |
| Synthetic 4096-byte round trip and interior offset transfers | Passed, byte-for-byte comparison |
| Invalid ranges, integer overflow, nulls, interior frees, double free, freed memory, foreign context | Rejected |
| Host-thread current-context isolation and explicit shared-context attachment | Passed, 2 threads |
| Context lifecycle | 32 create/allocate/free/destroy cycles, plus owned-allocation cleanup on context destruction |
| Unsupported compute capability / CUDA version query | NOT_SUPPORTED with output 0; no invented NVIDIA capability/version |
| Allocation-range unit test | Passed; observed fail against unimplemented stub first |
| Missing-export cleanup regression | Observed premature-return failure before fix; passed after macro returned lookup errors to caller handlers |
| M0 native kernel regression | All 16 B390 cases still pass after shared FFI extraction |
| C/Rust Level Zero ABI oracle | All fields, sizes and alignments match across 12 structures |
| Rust checks | Workspace tests (including explicit M0 GPU test), formatting and clippy with warnings denied passed |
| Publication checks | 6 Python tests passed, including staged/worktree mismatch, deleted past secret and annotated tag regression |

The first independent C host run failed because the DLL did not yet exist; the same host passed after implementation. Separate review found missing-export early returns and annotated-tag publication bypass; both were regression-tested and corrected. Targeted follow-up inspection confirmed both fixes.

## Reproduce

Requires Windows x64, Rust/MSVC, PowerShell 7 and the Intel native driver. No CUDA SDK, driver replacement or external Rust package download is required for this test.

```powershell
$env:CARGO_INCREMENTAL = '0'
pwsh -NoProfile -File scripts/run_m1_smoke.ps1
cargo test --workspace -- --include-ignored
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
python -m unittest discover -s tests -p test_public_artifacts.py -v
pwsh -NoProfile -File scripts/check_level_zero_abi.ps1
```

The ABI comparison additionally requires the pinned official header as described in M0-RESULTS.md. Build outputs are ignored under `target/` and `.cache/`. Raw machine-local results belong under ignored `results/local/`; this public summary contains only synthetic-test outcomes and minimal technical properties.

## Limits

This is experimental M1 infrastructure, not a released CUDA driver. No PTX parser, CUDA kernel/module execution, general nvcuda loading, primary context, cudart, AI library, AMD or broad CUDA-version compatibility has been established. C callers must provide valid non-null host pointers with sufficient memory. Device-loss, allocation failures and every native cleanup error are not fully fault-injected; uncertain contexts are poisoned and retained until process exit. No production recovery or complete NVIDIA error-precedence claim is made.

Next milestone: M2's PTX analysis and Intel code generation, built on this memory/context contract.
