# M3j / P03b: integer conversions and bit operations

Validated 2026-10-20 on Windows x64 / Intel Arc B390. This extends generic PTX
lowering after M3i; P03's wider arithmetic and ABI work remains incomplete.

## Accepted extension

- All16 cvt combinations between s32/u32/s64/u64, without modifiers. Signed
  source widening sign-extends, unsigned widening zero-extends, narrowing keeps
  low bits, same-width conversions preserve bits. Registers remain32/64-bit
  unsigned/bit containers; destination signedness introduces no extra extension.
- and/or/xor/not.b32/b64; shl.b32/b64; shr.b32/b64/u32/u64/s32/s64. Shift counts
  are always U32 at the PTX boundary. Logical shifts at/above width produce zero;
  signed right shifts preserve sign fill. Counts never reach a SPIR-V shift at
  or above its base width.
- The bounded U32 count is widened internally for64-bit SPIR-V shifts to avoid
  a native compiler failure observed with mixed-width shift operands on this
  driver. A focused binary-structure test failed before this normalization and
  passed afterwards; the full native matrix then passed.

No8/16-bit, vector/structure ABI, signed register declarations, negative-token
literals, float/integer conversion, saturation, rounding modifiers or new memory
types are added. Pointer/U32/F32 argument kinds and26 CUDA exports remain.
Inferred u64 pointer parameters still require the existing cvta-only proof;
integer cvt does not qualify an otherwise ambiguous parameter as a pointer.

## Native correctness evidence

[m3j_integer_check.py](../tests/m3j_integer_check.py) independently computes bit
results using Python integers and explicit masks. It generates bounded batches
of24 checks. Each PTX source reads a runtime U32 seed; source values and shift
counts depend on it, rather than being constant-only expressions. A PTX equality
comparison with the CPU bit result writes1.0 on success and0.0 on mismatch.
Every result starts as NaN and64 trailing floats are sentinels.

| Check | Actual result |
| --- | --- |
| CPU oracle cases |504:96 conversion,120 bitwise and288 shift cases |
| Inputs |Zero,one,signed extrema,all-one and alternating patterns; shift counts0,1,N-1,N,N+1,U32_MAX |
| Runtime seeds |0 and1, including source/count wraparound |
| PTX profiles |7.0/sm_50 and8.0/sm_52 |
| Containers |Raw PTX and genuine compressed nvFatbin for each profile/seed/batch |
| Successful matrix |168 images,4,032 boolean correctness checks and10,752 guards passed |
| Negative input |Unsupported saturating conversion and64-bit shift-count register rejected218/801/null |
| Recovery |Later compressed32-check fixture/64 guards passed; excluded from matrix totals |
| Baseline |Preserved M3i DLL/hash rejected the32-spelling fixture |
| Independent CUDA C/CLI |32 checks/64 guards passed through app-local staging and public CLI, bytes preserved |

The pinned producer's preprocessing removed the first source line in an initial
probe without a leading comment. The synthetic generator now follows the same
leading-comment convention as existing fixtures to retain the .version directive.
CT's metadata/body profile validation is unchanged; no fatbin decoder relaxation
or runtime source patch was introduced. Generated producer bytes are the actual
inputs tested and staged unchanged.

## Application and regressions

[integer_bits.ptx](../tests/fixtures/integer_bits.ptx) exercises all32 accepted
spellings. [m3j_cuda_app.c](../tests/m3j_cuda_app.c) is a separate synthetic host,
built against pinned official CUDA12.0.107 headers with normal nvcuda.dll imports.
It checks the fixture's32 results and64 guards. This is not an unchanged upstream
application or a direct NVIDIA execution comparison.

- Measured executable SHA-256: `3b87846cf1f2bb9932fe5b5355287c558b268da6a91d6c3032c159919360ca64`.
- Compressed input SHA-256: `20ed40f174964c3a552199380dd19e5c80148879b88d75c5e8f357f2814ef575`.

Rust69 workspace tests including prepared ignored native/producer checks and all
M3i failure probes passed. Python19 and all-target Clippy with warnings denied
passed. Rustfmt initially found one new test assertion needing wrapping; after
formatting, the check passed. The production DLL export table remained exactly26.
Actual M2 and M3h regressions passed, including the previous2D/3D matrix and
independent C/CLI consumer. Only the existing vendor-header anonymous-struct
warnings appeared in C builds. Rebuild executable hashes may differ.

## Reproduce and limitations

Preserve a built M3i DLL/hash in ignored .cache/m3j-baseline before changing
source; a new clone may build3fc185e separately without resetting another checkout.
Pinned producer/header prerequisites follow [M3d](M3d-RESULTS.md).

```powershell
$env:CARGO_INCREMENTAL = '0'
./scripts/run_m3j_smoke.ps1
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py'
python scripts/check_compatibility_profile.py
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
```

Official spirv-val was unavailable on PATH and skipped. Real NVIDIA comparison,
AMD, general signed arithmetic, broader argument ABI, and full P03 completion
remain unverified/unimplemented. Native results establish these bounded integer
cases, not general CUDA compatibility. Vendor/generated binaries and raw logs
remain ignored; only CT/synthetic source and sanitized evidence publish.

References: [PTX conversion table and shifts](https://docs.nvidia.com/cuda/archive/11.8.0/parallel-thread-execution/index.html),
[SPIR-V1.0](https://registry.khronos.org/SPIR-V/specs/1.0/SPIRV.html).
