# M3k / P03c: typed integer memory and explicit scalar ABI

Continue authorized generic CUDA translation after M3j1166739. No per-kernel
substitution. Extend global ld/st to b/u/s32 and b/u/s64, preserving raw bits in
width-matched registers. Add .s32/.s64 register aliases to existing bit containers.
IR Load/Store carries Ty; SPIR-V uses matching global pointer/value types and
explicit natural alignment4/8. Reject static byte offsets misaligned for width.

Param adds alignment:u32 metadata. Pointer .u64 .ptr .global .align accepts4/8;
existing unannotated .u64 inference stays Cvta-only, alignment4. Scalar .b64 and
.s64 map to a new U64 kind; .u32/.b32/.s32 map to U32. Scalar .f32 remains.
ld.param consumes matching width and bit/signed aliases. Unannotated .u64 is not
silently reclassified as a scalar. Packed/extra,8/16/vector/structure ABI remains
unsupported. Signedness is interpreted by operations, not host byte copying.

Conservative first-slice contract: an entry containing64-bit global memory
operations requires every pointer parameter declared align8. Pointer arguments
must start at that alignment and have at least alignment bytes in a current
allocation (4/8). Even an align8 pointer used only for32-bit data needs8 accessible
bytes under this restricted contract. Dynamic computed addresses/extents remain
trusted caller obligations, as with existing f32 access; this is not isolation.
Mixed4/8 pointer requirements in one wide-memory entry are later provenance work.

Alternative-profile identity compares full per-entry ordered (kind,alignment)
maps. U64 scalar and Pointer remain distinct even though both use8 host bytes.
CUDA marshals scalar8 bytes without allocation-range classification; pointer
arguments retain ownership/alignment/range checks. Exported signatures unchanged.

Tests first: typed parser/aliases/alignment and scalar-versus-pointer cases;
codegen pointer/load/store types; candidate ABI mismatch and host argument checks.
Actual Arc arrays compare exact integer bits including high64 bits, signed
extrema, odd sizes and interior pointers. Raw/compressed/alternative profiles,
multiple entries with different ABI, independent official-header C/CLI and
invalid-pointer recovery must pass. Preserve baseline hash/rejection. Run all
workspace/Python/failure tests and M2/M3h/M3j regressions. One independent review,
privacy scans, stacked draft PR, no merge; full P03 remains incomplete.

Sources: [PTX memory alignment](https://docs.nvidia.com/cuda/parallel-thread-execution/),
[OpenCL SPIR-V environment](https://registry.khronos.org/OpenCL/specs/unified/html/OpenCL_Env.html).
