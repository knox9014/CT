# M3k / P03c: typed integer memory and scalar64 ABI

Validated 2026-10-20, Windows x64 / Intel Arc B390. CT now lowers32/64-bit
integer global loads/stores and marshals explicitly declared64-bit integer
scalars through the existing CUDA Driver API connection. No kernel replacement.

## Accepted contract

- ld.global and st.global accept b32/u32/s32 and b64/u64/s64, alongside f32.
  Values retain their bits in width-matched registers. Signed register aliases
  .s32/.s64 map to the existing32/64-bit containers. No narrow-load extension
  into a wider destination register is added.
- Scalar .param .b64/.s64 is U64: eight host bytes, no pointer ownership
  classification. .u32/.b32/.s32 scalars are four bytes; f32 unchanged.
  Unannotated .param .u64 retains the conservative Cvta-only pointer inference;
  ambiguous scalaru64 is still rejected rather than silently reclassified.
- Explicit pointer .u64 .ptr .global .align accepts4/8. Param alignment is
  preserved through IR/codegen/runtime and alternative-image ABI identity.
  Pointer start and at least4/8 bytes must belong to the current allocation.
- An entry with64-bit global memory requires all its pointer parameters declared
  align8. This conservative restriction is per entry, not per module; xor32
  align4 and xor64 align8 coexist in the same module. Mixed4/8 pointer contracts
  inside a wide-memory entry need future provenance work. Even a pointer declared
  align8 but used only for32-bit data requires8 accessible bytes in this profile.
- Static offsets must be multiples of access size4/8. SPIR-V pointer/value types
  agree, with explicit natural memory alignment. Dynamic address alignment,
  extents and all kernel accesses remain trusted caller obligations.
- Alternative profiles compare complete ordered (kind,alignment) maps for all
  entry names. Scalar64 and pointer remain distinct despite both using8 bytes.
  Exported26 CUDA signatures, synchronous execution and failure containment stay.

## Actual native matrix

The synthetic [integer_memory.ptx](../tests/fixtures/integer_memory.ptx) has xor32,
xor64 and fill64 with different parameter lists. It uses one-element static
offsets and interior allocation pointers. The independent
[Python harness](../tests/m3k_memory_check.py) checks every output bit, including
high64 bits, and verifies read-only inputs byte-for-byte. Each payload starts
as the bitwise complement of its expected result, detecting missing writes.
There are65 prefix and64 suffix guards per case.

| Check | Actual result |
| --- | --- |
| Formats |Raw PTX, genuine plain/compressed nvFatbin and compressed alternative profiles |
| Entries/sizes/scalars |3 entries x6 sizes1/63/64/65/257/50000 x4 values x4 forms =288 cases |
| Integer outputs |2,421,600 exact integer values and37,152 guards passed |
| Input values |Zero,one,signed extrema,all-one,alternating and deterministic high-bit patterns |
| Scalar values |0,1,0x80000000fedcba98,U64_MAX;32-bit scalar uses low32 bits |
| Memory spellings |All b/u/s32/64 load/store aliases exercised across input forms |
| Alternative selection |Upper profile changes XOR to OR; CPU expects the selected operation |
| Invalid pointers per form |6: null,unowned,misaligned,one-past,4-byte allocation for align8,and foreign-context pointer; all INVALID_VALUE |
| Host scalar alignment |Unaligned8-byte host storage accepted via read_unaligned; full64-bit value preserved |
| Negative sources |Weak wide-pointer alignment, ambiguous u64 scalar and misaligned64-bit static offset rejected218/801/null |
| Alternative ABI conflict |Different pointer alignment rejected801/null |
| Baseline |Preserved M3j DLL/hash rejected the extension |

Pointer negatives use N=0, so an accidental acceptance would fail the assertion
without executing an unsafe GPU access. A valid65-element fill using unaligned
host scalar storage follows each negative set. These4x65 outputs/4x129 guards,
and the final65-output/129-guard source-rejection recovery, are excluded from288
case totals. Allocation extents are conservative checks, not a whole-kernel proof.

## Independent CUDA application

[m3k_cuda_app.c](../tests/m3k_cuda_app.c), built against pinned official CUDA12.0.107
headers, uses normal nvcuda.dll imports and no CT loader code. All three kernels
run with257 elements;771 exact integer outputs and387 guards passed. Fill's
U64_MAX scalar proves an unowned numeric value is not treated as a pointer.
App-local staging and public ct.py run both passed with executable/asset bytes
preserved. This consumer is synthetic, not an unchanged upstream application.

- Latest measured executable SHA-256: `f21ac918bc645e719fe58a0efc071daff6003e2a524d147c1e863d369856b000`.
- Compressed asset SHA-256: `1499843b4db208531be32cc6f9079a169dd87158c048c482642f3b1bef8ddcce`.

Rebuild executable hashes can differ. Only the two existing vendor-header
anonymous-struct warnings appeared; CT source had no new warnings.

## Review status

Author review of the complete production diff found no additional blocking
issue in typed load/store agreement, parameter alignment, scalar64 marshalling
or alternative-image ABI identity. This is author review only. The requested
independent reviewer could not start because its account usage limit was reached;
no independent review verdict was produced. Keep this change as a stacked draft,
with independent review pending before merge.

## Regression and reproduction

Rust73 including prepared ignored native/producer checks and all M3i failure
probes, Python19, rustfmt and warnings-denied all-target Clippy passed.
Actual M2/M3h/M3j/M3k scripts passed; the normal DLL exports exactly26 header
symbols. This does not imply full P03, unannotated scalaru64,8/16-bit,
vector/structure/packed ABI, general CUDA or AMD/NVIDIA execution support.

Preserve a built M3j DLL/hash in ignored .cache/m3k-baseline before changes;
new clones can build1166739 separately without resetting another checkout.
Pinned prerequisites follow [M3d](M3d-RESULTS.md).

```powershell
$env:CARGO_INCREMENTAL = '0'
./scripts/run_m3k_smoke.ps1
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py'
python scripts/check_compatibility_profile.py
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
```

Vendor/generated binaries, personal paths and raw logs remain ignored. Official
spirv-val, real NVIDIA comparisons and AMD execution remain separately unverified.
Memory and host pointers must be valid; CT is not an untrusted-code isolation
boundary. See [PTX alignment](https://docs.nvidia.com/cuda/parallel-thread-execution/)
and [OpenCL SPIR-V memory](https://registry.khronos.org/OpenCL/specs/unified/html/OpenCL_Env.html).
