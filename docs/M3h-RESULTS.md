# M3h / P03a: multidimensional CUDA execution

Validated 2026-10-20 on Windows x64 / Intel Arc B390, driver32.0.101.8622.
This implements the launch-dimension slice of P03; P03 integer/ABI expansion
and the general CUDA translator remain incomplete.

## Implemented contract

All twelve `%tid`, `%ntid`, `%ctaid`, `%nctaid` scalar `.x/.y/.z` components
lower to the corresponding component of shared SPIR-V builtin vectors. A module
still owns one native module with multiple independently scoped entries.
cuLaunchKernel forwards grid and block x/y/z to Level Zero without flattening.
Legacy single-axis Rust backend methods remain wrappers.

Every grid/block dimension must be nonzero and within the device's per-axis
limits. Grid limits are capped to I32_MAX to match attributes5..7. Block volume
must fit maxTotalGroupSize; checked u64 multiplication rejects overflow. Each
grid[i]*block[i] must fit U32_MAX. CUDA and native entry paths validate before
setting arguments or submitting work. Shared bytes, streams and extra remain
unsupported, with unchanged26 exports and Pointer/U32/F32 argument kinds.

## Measured execution

The synthetic [PTX fixture](../tests/fixtures/multidimensional.ptx) contains a
coordinate diagnostic and a bounded row-major matrix/volume addition kernel.
The diagnostic writes all12 special-register values for every launched thread
through a read-only f32 lookup table because numeric conversion is outside this
slice. Independent CPU nested loops enumerate block and thread coordinates.
Every output starts as NaN and every trailing guard has a distinct sentinel.

| Check | Actual result |
| --- | --- |
| Raw and genuine compressed nvFatbin |26 cases,37,394 outputs and4,856 guards passed |
| Diagnostic shapes per image |8 successive shapes, including unit axes, asymmetric2D/3D and repeated shapes on the same handles |
| Matrix/volume shapes per image |1x1x1,17x13x1,13x11x5,65x7x3,3x19x7; partial blocks and entire padded dispatch guarded |
| Invalid dimensions per image |16 shapes,32 calls with valid/null parameter arrays, all INVALID_VALUE; no output writes |
| Unsupported launch options per image |3 rejections for shared bytes, stream and extra, all801 |
| Recovery per image |Later valid2x3x2 grid /3x2x2 block executed correctly; extra1,728 outputs/64 guards excluded from26-case totals |
| Baseline |Preserved M3g DLL rejected the new fixture with218/null; hash verified before use |
| Advertised limits on this device |Block total/x/y/z1024; grid x/y/z2,147,483,647 |
| Independent synthetic C application |2D and3D shapes on the same handle;936 outputs and632 guards passed via staging and public CLI |

The invalid tests cover every zero axis, per-axis limit+1, oversized block volume
and per-axis global-size overflow. Pure Rust tests also exercise asymmetric
device limits and u64 block-volume overflow. Giant accepted launches were not
submitted. Rejection and recovery evidence is separate from successful matrix
counts. CPU oracles and harnesses are in
[m3h_dimensions_check.py](../tests/m3h_dimensions_check.py).

## CUDA application path and privacy

[m3h_cuda_app.c](../tests/m3h_cuda_app.c) is an independent synthetic consumer
built against pinned official CUDA12.0.107 headers with normal nvcuda.dll imports.
It loads the same genuine compressed fatbin, checks grid attributes and stale
function rejection after unload. Both app-local staging and public ct.py run
preserved application and input bytes. This is not an unchanged upstream app.

- Measured executable SHA-256: `750a910505891b3d9fabf1723989cf903fbe6a4d3c7a6bbb1d827f51df7b1bfb`.
- Compressed fatbin SHA-256: `133f9d6d3fe4ddeae7717835ec47ee899ed838153b747d3313c659ce5fe86e80`.

Fresh rebuild hashes may differ. Official vendor headers emitted two anonymous
struct-extension warnings; the CT consumer source built and executed. Vendor
packages, native binaries, generated assets, local paths and raw logs remain
ignored. Only synthetic source, CT code, harnesses and sanitized results publish.

## Reproduce and verification limits

Preserve a built M3g DLL/hash at ignored .cache/m3h-baseline before changing source;
on a new clone build03478d3 separately, without resetting another checkout.
Use the pinned producer/header prerequisites in [M3d](M3d-RESULTS.md).

```powershell
$env:CARGO_INCREMENTAL = '0'
./scripts/run_m3h_smoke.ps1
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py'
python scripts/check_compatibility_profile.py
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
```

Rust48 tests including prepared native/producer checks, Python19, formatting and
Clippy passed. Native ABI12 structures and M1/M2/M3c/M3f/M3g regression scripts
passed, including M3g's1,000 module cycles. The M2 negative launch test now uses
zero grid Y (INVALID_VALUE) because a positive Y dimension is supported.
Official SPIR-V validator was unavailable on PATH and skipped;
native Intel compilation/execution is a separate check. AMD, NVIDIA execution
and coexistence, device loss and full CUDA error precedence remain unverified.
No new arithmetic, vector/structure ABI, Runtime, shared/warp/barrier, stored
global or device-function support is claimed.

References: [PTX special registers](https://docs.nvidia.com/cuda/parallel-thread-execution/index.html),
[Level Zero device limits](https://oneapi-src.github.io/level-zero-spec/level-zero/1.18.31/core/api/apis/device.html).
