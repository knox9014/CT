# Experimental PTX profile through M3o

CT parses instructions into typed control-flow IR and emits SPIR-V 1.0 Kernel/OpenCL with Physical64 addressing. Intel Level Zero compiles and executes it. Kernel names do not select replacement implementations.

## Module shape

- ASCII, at most 256 KiB and 65,536 tokens. Comments: `//` and nonnested `/* ... */`.
- Exactly PTX7.0/sm_50 or PTX8.0/sm_52, `.address_size 64`, and1..32 distinct `.visible .entry` or module-local `.entry` kernels. P09a2 accepts the latter for genuine nvcc static kernels; separate modules may have identical entry names with different implementations. Names still cannot collide within a module. `.extern`/`.weak` entries and device-function linking remain unsupported. Accepting these headers does not imply all instructions in either PTX version are supported. M3g emits one SPIR-V/native module with independently scoped functions; legacy Rust parse/translate still require one entry.
- Pointer parameters: `.param .u64 .ptr .global .align 4/8 name`. Scalars: `.u32/.b32/.s32` (U32), `.b64/.s64` (U64) or `.f32`. Unannotated `.u64` follows the bounded pointer/scalar classification below.
- Unannotated `.param .u64` uses conservative pointer/scalar classification. Pointer loads require a single definition and uses through `cvta.to.global.u64`. Unloaded parameters and the explicitly permitted U64 integer-use patterns may be scalar; mixed pointer/scalar or unrecognized uses are rejected. This is not arbitrary CUDA argument-ABI inference. See `classify_unannotated_u64` in `crates/ct-ptx/src/parser.rs` and the Numba boundary in [the current analysis](../CT-STATUS-ANALYSIS-2026-11-13.md).
- At most256 module globals before entries: scalar `.global .align 4 .u32` or `.global .align 8 .u64` with zero/single integer initialization and typed direct ordinary/volatile loads/stores. Both widths emit shared native storage with host access. `.global .align 8 .b8 name[N]` (N=1..4096) remains unused metadata only, without storage; arrays/constants/externs/address-taking and named offsets remain unsupported.
- Registers: `.pred`, `.u32`/`.b32`/`.s32`, `.u64`/`.b64`/`.s64`, `.f32`; declarations precede executable instructions. Signed aliases store bits; instruction variants determine interpretation. Arrays such as `%r<5>` expand into registers.
- Per entry: at most256 registers,128 blocks,4,096 non-control instructions and32 parameters. Register/parameter/label scopes are independent. Identifiers use letters, digits, `_`, `$`, without a leading digit; maximum256 ASCII bytes. Single `_` or `$` is rejected. Duplicate entry names or collisions with module globals are rejected.
- All blocks must be reachable. Every register must be defined on every incoming path before use, including loop-carried values.

Standalone `.common .global .align 8 .u64` declarations without initializers are accepted within the existing bounded module. This permits observed producer declarations, not cross-object common-symbol resolution or a device linker.

Integer instruction constants support decimal, `0x` hexadecimal and leading-zero octal, with one optional unary `+`/`-`. Positive magnitudes fit the operand width; negative magnitude is at most2^(width-1), converted to two's-complement bits. Invalid octal such as `08` is rejected. No U suffix, compound expression, signed register/builtin/float/predicate or signed address-offset/initializer support. Floating constants use `0fXXXXXXXX` bit notation. This is narrower than full PTX syntax; see [M3o evidence](../M3o-RESULTS.md).

## Instructions

| Family | Accepted spellings |
| --- | --- |
| Parameters | `ld.param.u/b/s32`, `ld.param.u/b/s64`, `ld.param.f32`, matching parameter width/kind |
| Global memory | `ld.global`/`st.global` `.u/b/s32`, `.u/b/s64`, `.f32`; 64-bit address with optional nonnegative naturally aligned byte offset4/8 |
| Move/address | `mov.u32`, `mov.b32`, `mov.s32`, `mov.u64`, `mov.b64`, `mov.s64`, `mov.f32`, `cvta.to.global.u64` |
| Modular integer arithmetic | `add/sub/mul.lo/mad.lo` for `.s32/.u32/.s64/.u64`; low-width result bits, including overflow |
| Other integer arithmetic | `mul.wide.u32`, `div.u32`, `rem.u32`; `mul.wide.s32` sign-extends both operands before a64-bit product |
| Integer extrema/unary | `min/max.s32/u32/s64/u64`, `abs/neg.s32/s64`; no packed/relu variants |
| Floating arithmetic | `add.f32`, `mul.f32`, `sub.f32`, optionally with `.rn` before `.f32`; SPIR-V Kernel `ContractionOff` on every entry prevents contraction across separate operations |
| Fused arithmetic | Exact scalar `fma.rn.f32`, explicit OpenCL.std fma26; one nearest-even rounding of product plus sum, with separate ordinary multiply/add retained |
| Integer predicates/select | `setp.eq/ne/lt/le/gt/ge` for `.s32/.u32/.s64/.u64`; `selp.b/u/s32`, `selp.b/u/s64`; one predicate destination, no predicate combining |
| Float predicates/select | `setp.lt.f32`, `setp.ge.f32`, `selp.f32` |
| Control flow | labels, `bra`, `@%predicate bra`, `@!%predicate bra`, `ret` |
| Special registers | Scalar `.x/.y/.z` of `%tid`, `%ntid`, `%ctaid`, `%nctaid`; U32 operands |
| Integer conversion | All16 `cvt.{s32,u32,s64,u64}.{s32,u32,s64,u64}` pairs; no modifiers, width-matched bit/unsigned registers |
| Bitwise | `and/or/xor/not.b32`, `.b64`; predicate forms excluded |
| Shift | `shl.b32/b64`, `shr.b32/b64/u32/u64/s32/s64`; U32 count at either width |

The relaxed-memory extension permits U64 bit-container registers with
`ld.global.u32/b32` and `st.global.u32/b32`: loads zero-extend, stores keep
only the low 32 bits, and memory accesses retain their 4-byte width/alignment.
Named scalar u32 globals also permit the wider register with existing ordinary
or volatile `.u32` operations; named `.b32` and volatile pointer accesses remain
outside the profile. Widened signed/float, param and cvt operands are not added.
This operand-width change itself does not relax pointer alignment. The separate
access-specific analysis below governs wide addresses. The first numerical
fixture is synthetic; later genuine producer evidence is recorded separately.

M3j integer conversions sign-extend signed sources on widening, zero-extend
unsigned sources, truncate low bits on narrowing and preserve same-width bits.
Logical shifts with counts >= width return zero; arithmetic right shifts return
sign fill. Bounded counts avoid undefined SPIR-V shifts;64-bit shifts normalize
the bounded count internally to the base width. No float conversion, saturation or8/16-bit types are implied. Scalar64 ABI is the separate M3k extension below. See [M3j evidence](../M3j-RESULTS.md).

Unknown directives/modifiers, unsupported predication and mismatched types are rejected. Signed operations interpret existing 32/64-bit register contents; signed register declarations are bit-container aliases; negative integer immediates use the bounded M3o rule above. Signed tests include both literal signs and hexadecimal two's-complement bits. Signed division, saturation/carry/high-result variants, division by zero, NaNs, infinities, denormals and uncommon rounding behavior remain outside the validated workload. Modular multiply/add uses width-matched integer operations at both stages; see [M3l evidence](../M3l-RESULTS.md). Finite test inputs do not establish full PTX floating-point conformance.

## Launch and trust boundary

Launches are synchronous with1D/2D/3D grid/block dimensions. Every axis must be nonzero and within native device limits; grid counts are capped to I32_MAX and advertised by attributes5..7. Block volume must fit maxTotalGroupSize (checked u64 multiplication), and grid[i]*block[i] must fit U32_MAX for each axis. Native Driver streams and dynamic shared memory are unsupported; bounded Runtime streams are ordered by the Runtime worker. `kernelParams` points to host storage of 8 bytes per device pointer/U64 scalar and4 bytes per U32/F32 scalar. Packed `extra` uses the same slot widths with natural alignment. See [M3h evidence](../M3h-RESULTS.md); this is only the dimension slice of P03.

Pointer arguments require their declared/inferred4/8-byte alignment and at least4/8 bytes in a current-context allocation. For each64-bit register-address access, CT now requires a unique pointer-parameter origin and a proved zero residue modulo8 for the computed address plus immediate offset. Mixed align4/8 pointer entries are supported; unrelated/narrow-only pointers remain4. Validated unannotated pointers used by wide accesses acquire an8-byte launch contract; explicit align4 roots are never upgraded. The existing native signature and launch base-alignment/minimum-extent checks consume that contract. Explicit align8 parameters still require8 bytes even for narrow-only accesses.

The bounded CFG analysis tracks mov/cvta, same-width64 conversion, pointer-plus-scalar/minus-scalar, scalar low-bit arithmetic and literal left shifts; joins retain identical origins and union possible low bits. Loops are checked after convergence, with a4096 block-visit budget; exhaustion rejects. Scalar/loaded/constant addresses, mixed-origin joins, unsupported pointer operations and uncertain wide alignment are rejected. Named typed globals retain separate storage alignment. This intentionally narrows old acceptance of unproved scalar addresses. Narrow-address analysis is not expanded by this change.

This is an alignment/provenance proof, not an access-extents or ownership proof for derived addresses. Callers must provide valid extents, initialized inputs and terminating trusted code. CT is not an isolation boundary for untrusted PTX. Arbitrary C host pointers must also be valid and sufficiently sized. [M3k evidence](../M3k-RESULTS.md) is historical; the newer access-specific contract supersedes its all-pointer alignment restriction.

Module/function handles belong to their creating context. Unload invalidates its functions; context destruction invalidates all owned handles. Uncertain native completion or cleanup poisons the context and retains possibly live resources until process exit.

PTX source is not retained as module metadata or written to logs. No translated binary cache is published. Cubins, general nvcc output, full cudart/CUDA libraries, atomics, general shared memory and warp semantics are unsupported. The [raw fatbin profile](fatbin-profile.md) accepts bounded plain/LZ4 alternatives and M3f selects one known profile with matching entry/argument kinds; M3g supports1..32 entries and compares complete entry-name/ordered-kind maps. Historical ASCII PTX under a `.fatbin` filename remains supported. See [M3c results](../M3c-RESULTS.md), [M3d results](../M3d-RESULTS.md), [M3e results](../M3e-RESULTS.md), [M3f results](../M3f-RESULTS.md) and [M3g results](../M3g-RESULTS.md).

References: [PTX 7.0](https://docs.nvidia.com/cuda/archive/11.0/parallel-thread-execution/index.html), [SPIR-V registry](https://registry.khronos.org/SPIR-V/), [Level Zero specification](https://oneapi-src.github.io/level-zero-spec/level-zero/latest/).


## Uniform block barrier profile

Canonical decimal `bar.sync 0;` supports an entire CTA rendezvous. A kernel using
it must have CTA-uniform control flow as proved below, including loop backedges.
Predicated barriers, counted/nonzero/dynamic IDs, warp, arrive/reduction and cluster
forms are rejected before GPU submission. Kernels without barriers/shared storage
retain existing CFG support. The proof is repeated at parser/emitter boundaries.

SPIR-V is a real OpControlBarrier224: Workgroup execution2, Workgroup memory2,
SequentiallyConsistent16 plus WorkgroupMemory256 and CrossWorkgroupMemory512
(0x310). This supplies ordering for CTA shared/global memory and respects the
[OpenCL1.2 barrier environment rules](https://registry.khronos.org/OpenCL/specs/unified/html/OpenCL_Env.html).
The stronger memory order is deliberate; no optimization/performance claim.
Exact opcode/constants/control-flow checks supplement the pinned validator,
which alone is not a proof of PTX rendezvous semantics. Neither semantic mutation
nor invalid barrier kernels are executed on a GPU.

Bounded static shared allocation/addressing is implemented below. This profile
does not establish matrixMul execution, partial CTA participation, dynamic shared memory,
warp/subgroup operations, general divergent control flow or grid synchronization.
See [barrier implementation plan](../superpowers/plans/2026-10-27-uniform-block-barrier.md).

## Initial static shared storage

Per-kernel `.shared .align {4,8,16} .b8 name[N]` and `.u32/.b32/.f32`
arrays are supported before executable instructions. Extents must be positive,
divisible by4 bytes, at most16 objects and16384 bytes/kernel after rounding each
object size to its declared alignment. No initializers, module-level/extern or
dynamic shared storage. A shared kernel must have CTA-uniform control flow.

`ld/st.shared` and `ld/st.volatile.shared` support exact-width U32/B32/F32 values.
Address operands may be a shared symbol or a32/64-bit register plus nonnegative
word-aligned byte offset. `mov` of a symbol, `add` with scalar byte offsets,
unsigned U32->U64 widening and proven `cvta.to.shared.u64` retain object identity.
Other shared pointer operations, address escape, mixing roots and crossing into
global memory are rejected. A bounded CFG proof tracks mod4 alignment and
clears constant-value knowledge across scalar integer width conversions.

Each object lowers to a distinct per-kernel Workgroup U32 array, decorated with
its alignment. AccessChain uses the relative byte offset divided by4. F32 loads
and stores bitcast values, keeping pointer storage classes unchanged. Shared
addresses never lower to physical CrossWorkgroup pointer conversions. Canonical
block barriers supply rendezvous and visibility between initialized phases.

Known constant extent violations are rejected; dynamic index bounds, launch
dimensions and race freedom remain program obligations. Uninitialized shared
storage has no zero-initialization guarantee. No U64/vector/atomic accesses,
dynamic shared launch bytes, partial CTA barriers or general divergent CFG support.
See [shared implementation plan](../superpowers/plans/2026-10-27-static-shared-memory.md).

## CTA-uniform control flow

For any shared/barrier kernel, every conditional branch must have a CTA-uniform
predicate after fixed-point analysis. Scalar/pointer parameter values, constants,
`%nctaid`, `%ntid` and `%ctaid` are uniform within the block. `%tid` and every
global/shared memory load result are conservatively varying. Compute results
are uniform only if all inputs are uniform; joins AND facts. Entry input stays
nonuniform even with backedges. This proves identical control decisions across
the CTA without relying on warp scheduling or the `.uni` spelling.

Both `bra` and `bra.uni`, unconditional or predicated, use this proof. The exact
nvcc `.pragma "nounroll";` is accepted as metadata; other pragma strings remain
unsupported. Native compiler optimization is not guaranteed by this metadata.
Loops may use uniform loop-carried registers; uninitialized entry values and
unreachable blocks are rejected. Every block must have a possible path to Return.
The proof does not establish runtime termination: trusted callers must use valid
finite iteration arguments and initialized/in-bounds memory.

Uniform and shared analyses each reject on4096 block visits or65536 interpreted
instructions, including final checks. Existing128-block/256-register/4096-static-
instruction limits remain. Shared joins retain only identical must-origins,
union residues, keep equal known values, and OR a separate possible-shared taint.
Mixed roots cannot be accessed; any possible shared address is rejected by
escape/global-memory/unsupported-operation checks. Invalid intermediate transfers
widen to conservative facts; only converged states are used for final checking
and per-instruction object roots. This is not a complete type verifier for arbitrary
manually constructed public IR; parser arity/type checks remain required.

General divergent reconvergence, memory-driven uniformity inference, warp/cluster
barriers and whole-program termination proof remain outside the profile.
See [uniform control plan](../superpowers/plans/2026-10-27-uniform-control-flow.md).

## Fused binary32 slice

Only `fma.rn.f32 dst,a,b,c` is supported: exact-width F32 registers/bit literals,
three inputs and one destination. Other rounding modes, missing rounding, ftz/sat,
F64/F16/packed forms and mad aliases remain rejected. Emission rechecks this
operation's type/arity contract for public IR. One lazy `OpenCL.std` import is
emitted before OpMemoryModel and shared by all entries; OpExtInst fma26 expresses
the fused operation. ContractionOff continues preventing implicit fusion of
ordinary multiply/add sequences. No fast-math or denorm-flush flags are added.

Current Intel/compiler-mode diagnostics compare finite/inf/signed-zero bits and
subnormal boundary behavior against exact integer arithmetic and a CPU reference
configured for nearest-even with FTZ/DAZ disabled. NaNs are compared by class;
payload/sign are unspecified. This is bounded test evidence, not exhaustive
IEEE754 conformance or another-device floating-point-mode validation.

matrixMul offline triage schema3 distinguishes rejected translation from a
translated module. Successful output is structurally summarized and hash-pinned,
with `validation=not_run` until separately validated. Import/translation closure
keeps application compatibility unproven and never runs the EXE or GPU kernels.
Older schema2 rejection evidence is not relabelled as schema3 success.
See [FMA implementation plan](../superpowers/plans/2026-10-27-fused-f32.md).

## Bounded original matrix kernel diagnostic

The unchanged, pinned matrixMul PTX module has a Driver-only execution harness
for its original tile16/tile32 entries and five-argument C,A,B,wA,wB ABI. Closed
(tile,M,K,N) cases are (16,16,16,16), (16,32,48,64), (32,32,32,32), (32,64,64,96).
All dimensions are positive tile multiples. The worker queries attributes1..7
and preflights every case, including1024 threads/group, before any launch.

Input A coefficients[-8,8]/8 and B[-9,9]/16 keep all partial sums exactly F32.
The parent checks integer dot products/128 for all9472 output words per seed,
all A/B bytes unchanged and16-word guards on both ends of each buffer. GPU buffers
are initialized to NaN before uploads. Identical workers run through nominal CT
and existing no-launch/no-copy forwarding DLLs; API success alone is insufficient.
Controls require exact initial-buffer/NaN-poison signatures and numerical failure.

Raw PTX bytes, providers, job inputs and complete readbacks are hash-pinned. The
worker rejects optimized Python, unqualified geometry, changed PTX, stale outputs
and invalid jobs before loading/launching. It explicitly synchronizes and only
reports API completion after cleanup; the parent performs numerical acceptance.
The known raw PTX SHA-256 is
`999de47c5a9d2610641f37fd5a949523d3e29c3b6c257d5dff7f65e9359ec07b`.

This is execution of original kernels through a custom CT Driver consumer.
The original matrixMul executable, device-selection policy and complete Runtime
application path are not executed or established by this diagnostic. Other
dimensions/data/device profiles, performance and release readiness remain
unverified. See [kernel execution plan](../superpowers/plans/2026-10-27-original-matrix-kernels.md).

### Device static shared capacity

The authoritative translator limit is `ct_ptx::MAX_STATIC_SHARED_BYTES=16384`.
Compiled entries retain their aligned static-shared byte requirement (each object
rounded to its declared alignment). Driver attribute8 reports the smaller of the
native Level Zero maxSharedLocalMemory and that CT bound. Module loading checks
every entry individually against the owning context device before native creation;
independent entry budgets are not added together. Zero-native-capacity devices can
still load zero-shared kernels. Native compiler/resource errors can still occur
within this conservative declaration budget. Nonzero dynamic shared launch bytes
remain unsupported. This policy does not establish a virtual NVIDIA architecture.
Fatbin selection checks every candidate's translation, metadata, duplicate profile,
global identity and entry ABI before capacity affects selection. Among fitting
candidates, PTX8.0/sm52 ranks above PTX7.0/sm50, independent of record order. Every
entry must fit the owning device's bounded capacity. Nonfitting valid alternatives
may be skipped; malformed or unsupported alternatives still reject the entire
input. If none fits, return801. Raw/single candidates follow the same capacity
rule. The final pre-native capacity gate remains. Native compiler/resource errors
propagate without trying other variants.
