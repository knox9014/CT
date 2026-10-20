# M3j / P03b: bounded integer conversion and bit operations

User authorized continuing P03 after M3i failure checks. Base3fc185e. Extend
generic PTX lowering, preserve the CUDA connection, existing26exports and ABI.

Accept16 unsaturated cvt.{s32,u32,s64,u64}.{s32,u32,s64,u64} combinations.
Registers remain U32/U64 bit containers (.b32/.u32 and .b64/.u64). Signed source
widening sign-extends; unsigned widening zero-extends; narrowing keeps low bits;
same-width conversion preserves bits. Destination signedness affects no further
extension because destination register width equals the format width here.
Keep8/16-bit, floats, rounding/saturation, signed register declarations, integer
parameter ABI and negative-token literals outside this slice.

Accept and/or/xor/not.b32/b64, shl.b32/b64, and shr.b32/b64/u32/u64/s32/s64.
Shift counts are U32 even for64-bit values. Counts >= width produce zero for
logical shifts and sign fill for arithmetic shifts. Lower shifts using a bounded
count <= width-1 before the SPIR-V shift; a select supplies zero for oversized
logical shifts. Never execute a SPIR-V shift with count >= base width.

IR uses Op::Convert{to:Ty,signed:bool} (signed source) and explicit bit/shift ops;
Compute.ty remains source/base width. Pointer proof must remain conservative:
new integer conversions must not qualify inferred integer u64 parameters as
pointers. No new memory type or per-kernel replacement is introduced.

Evidence: test-first parser operand/width/malformed cases; emitted SPIR-V
conversion/shift opcode and safe-count structure inspection; CPU integer oracle
against runtime-seeded synthetic kernels on Arc, boundary patterns and counts
0/1/N-1/N/N+1/U32_MAX, both widths/signs and all16 conversions. Raw and genuine
compressed fatbins, known PTX profiles and independent normal-import C/CLI path
must pass. Preserve M3i DLL/hash for baseline rejection. Re-run workspace,
Python, M2/M3h normal GPU paths and private failure tests. One independent review,
privacy scans and stacked draft PR; no merge or general P03 completion claim.

Sources: [PTX scalar conversion table and shift definitions](https://docs.nvidia.com/cuda/archive/11.8.0/parallel-thread-execution/index.html),
[SPIR-V1.0](https://registry.khronos.org/SPIR-V/specs/1.0/SPIRV.html).
Opcode numbers checked against the already pinned Khronos grammar. Real NVIDIA
execution, AMD and official spirv-val remain separately verified or skipped.
