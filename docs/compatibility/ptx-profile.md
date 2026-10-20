# Experimental PTX profile through M3l

CT parses instructions into typed control-flow IR and emits SPIR-V 1.0 Kernel/OpenCL with Physical64 addressing. Intel Level Zero compiles and executes it. Kernel names do not select replacement implementations.

## Module shape

- ASCII, at most 256 KiB and 65,536 tokens. Comments: `//` and nonnested `/* ... */`.
- Exactly PTX7.0/sm_50 or PTX8.0/sm_52, `.address_size 64`, and1..32 distinct `.visible .entry` kernels. Accepting these headers does not imply all instructions in either PTX version are supported. M3g emits one SPIR-V/native module with independently scoped functions; legacy Rust parse/translate still require one entry.
- Pointer parameters: `.param .u64 .ptr .global .align 4/8 name`. Scalars: `.u32/.b32/.s32` (U32), `.b64/.s64` (U64) or `.f32`. Unannotated `.u64` is still inferred pointer-only under the rule below.
- Unannotated `.param .u64` is accepted only with conservative pointer proof: at least one parameter load; each loaded register has one definition and is used only by `cvta.to.global.u64`. Ambiguous, unused or integer u64 scalar parameters are rejected.
- At most256 unused module-global declarations before all entries: `.global .align 8 .u64 name` with optional integer initializer, or `.global .align 8 .b8 name[N]` for N=1..4096 with optional exactly N byte initializers. Names/initializers are validated; global references and global lookup APIs remain unsupported. No storage is emitted for these unobservable unused globals.
- Registers: `.pred`, `.u32`/`.b32`/`.s32`, `.u64`/`.b64`/`.s64`, `.f32`; declarations precede executable instructions. Signed aliases store bits; instruction variants determine interpretation. Arrays such as `%r<5>` expand into registers.
- Per entry: at most256 registers,128 blocks,4,096 non-control instructions and32 parameters. Register/parameter/label scopes are independent. Identifiers use letters, digits, `_`, `$`, without a leading digit; maximum128 characters. Single `_` or `$` is rejected. Duplicate entry names or collisions with module globals are rejected.
- All blocks must be reachable. Every register must be defined on every incoming path before use, including loop-carried values.

Integer constants support decimal, `0x` hexadecimal and leading-zero octal. Invalid octal such as `08` is rejected. Floating constants use `0fXXXXXXXX` bit notation. This is narrower than full PTX syntax.

## Instructions

| Family | Accepted spellings |
| --- | --- |
| Parameters | `ld.param.u/b/s32`, `ld.param.u/b/s64`, `ld.param.f32`, matching parameter width/kind |
| Global memory | `ld.global`/`st.global` `.u/b/s32`, `.u/b/s64`, `.f32`; 64-bit address with optional nonnegative naturally aligned byte offset4/8 |
| Move/address | `mov.u32`, `mov.b32`, `mov.u64`, `mov.b64`, `mov.f32`, `cvta.to.global.u64` |
| Modular integer arithmetic | `add/sub/mul.lo/mad.lo` for `.s32/.u32/.s64/.u64`; low-width result bits, including overflow |
| Other integer arithmetic | `mul.wide.u32`, `div.u32`, `rem.u32`; `mul.wide.s32` sign-extends both operands before a64-bit product |
| Floating arithmetic | `add.f32`, `mul.f32`, `sub.f32`, optionally with `.rn` before `.f32`; separate operations carry SPIR-V NoContraction |
| Predicates/select | `setp.ge.u32`, `setp.lt.u32`, `setp.eq.u32`, `setp.lt.f32`, `setp.ge.f32`, `selp.f32` |
| Additional predicates | `setp.ge.s32`, `setp.lt.s32`, `setp.eq.u64` |
| Control flow | labels, `bra`, `@%predicate bra`, `@!%predicate bra`, `ret` |
| Special registers | Scalar `.x/.y/.z` of `%tid`, `%ntid`, `%ctaid`, `%nctaid`; U32 operands |
| Integer conversion | All16 `cvt.{s32,u32,s64,u64}.{s32,u32,s64,u64}` pairs; no modifiers, width-matched bit/unsigned registers |
| Bitwise | `and/or/xor/not.b32`, `.b64`; predicate forms excluded |
| Shift | `shl.b32/b64`, `shr.b32/b64/u32/u64/s32/s64`; U32 count at either width |

M3j integer conversions sign-extend signed sources on widening, zero-extend
unsigned sources, truncate low bits on narrowing and preserve same-width bits.
Logical shifts with counts >= width return zero; arithmetic right shifts return
sign fill. Bounded counts avoid undefined SPIR-V shifts;64-bit shifts normalize
the bounded count internally to the base width. No float conversion, saturation or8/16-bit types are implied. Scalar64 ABI is the separate M3k extension below. See [M3j evidence](../M3j-RESULTS.md).

Unknown directives/modifiers, unsupported predication and mismatched types are rejected. Signed operations interpret existing 32/64-bit register contents; signed register declarations are bit-container aliases; negative-token immediates remain unsupported. Synthetic signed tests use hexadecimal two's-complement bits. Signed division, saturation/carry/high-result variants, division by zero, NaNs, infinities, denormals and uncommon rounding behavior remain outside the validated workload. Modular multiply/add uses width-matched integer operations at both stages; see [M3l evidence](../M3l-RESULTS.md). Finite test inputs do not establish full PTX floating-point conformance.

## Launch and trust boundary

Launches are synchronous with1D/2D/3D grid/block dimensions. Every axis must be nonzero and within native device limits; grid counts are capped to I32_MAX and advertised by attributes5..7. Block volume must fit maxTotalGroupSize (checked u64 multiplication), and grid[i]*block[i] must fit U32_MAX for each axis. Streams, dynamic shared memory and packed `extra` arguments are unsupported. `kernelParams` points to host storage of 8 bytes per device pointer/U64 scalar and4 bytes per U32/F32 scalar. See [M3h evidence](../M3h-RESULTS.md); this is only the dimension slice of P03.

Pointer arguments require declared4/8-byte alignment and at least4/8 bytes in a current-context allocation. Any entry with64-bit global access requires every pointer parameter explicitly align8; mixed align4/8 pointers in such an entry are not yet supported. Even align8 pointers used only for32-bit data conservatively require8 bytes. Scalar64 copies8 bytes without pointer classification. This cannot prove subsequent computed-address alignment or access extents. Callers must provide valid aligned extents, initialized inputs and terminating trusted code. CT is not an isolation boundary for untrusted PTX. Arbitrary C host pointers must also be valid and sufficiently sized. See [M3k evidence](../M3k-RESULTS.md).

Module/function handles belong to their creating context. Unload invalidates its functions; context destruction invalidates all owned handles. Uncertain native completion or cleanup poisons the context and retains possibly live resources until process exit.

PTX source is not retained as module metadata or written to logs. No translated binary cache is published. Cubins, general nvcc output, cudart, CUDA libraries, atomics, shared memory and warp semantics are unsupported. The [raw fatbin profile](fatbin-profile.md) accepts bounded plain/LZ4 alternatives and M3f selects one known profile with matching entry/argument kinds; M3g supports1..32 entries and compares complete entry-name/ordered-kind maps. Historical ASCII PTX under a `.fatbin` filename remains supported. See [M3c results](../M3c-RESULTS.md), [M3d results](../M3d-RESULTS.md), [M3e results](../M3e-RESULTS.md), [M3f results](../M3f-RESULTS.md) and [M3g results](../M3g-RESULTS.md).

References: [PTX 7.0](https://docs.nvidia.com/cuda/archive/11.0/parallel-thread-execution/index.html), [SPIR-V registry](https://registry.khronos.org/SPIR-V/), [Level Zero specification](https://oneapi-src.github.io/level-zero-spec/level-zero/latest/).
