# Experimental M2/M3c PTX profile

CT parses instructions into typed control-flow IR and emits SPIR-V 1.0 Kernel/OpenCL with Physical64 addressing. Intel Level Zero compiles and executes it. Kernel names do not select replacement implementations.

## Module shape

- ASCII, at most 256 KiB and 65,536 tokens. Comments: `//` and nonnested `/* ... */`.
- Exactly PTX7.0/sm_50 or PTX8.0/sm_52, `.address_size 64`, and one `.visible .entry`. Accepting these headers does not imply all instructions in either PTX version are supported.
- Pointer parameters: `.param .u64 .ptr .global .align 4 name`. Scalars: `.param .u32 name` or `.param .f32 name`.
- Unannotated `.param .u64` is accepted only with conservative pointer proof: at least one parameter load; each loaded register has one definition and is used only by `cvta.to.global.u64`. Ambiguous, unused or integer u64 scalar parameters are rejected.
- At most 256 unused module-global declarations before the entry: `.global .align 8 .u64 name` with optional integer initializer, or `.global .align 8 .b8 name[N]` for N=1..4096 with optional exactly N byte initializers. Names/initializers are validated; global references and global lookup APIs remain unsupported. No storage is emitted for these unobservable unused globals.
- Registers: `.pred`, `.u32`/`.b32`, `.u64`/`.b64`, `.f32`; declarations precede executable instructions. Arrays such as `%r<5>` expand into registers.
- At most 256 registers, 128 blocks and 4,096 non-control instructions. Identifiers use letters, digits, `_`, `$`, without a leading digit; maximum 128 characters. Single `_` or `$` is rejected.
- All blocks must be reachable. Every register must be defined on every incoming path before use, including loop-carried values.

Integer constants support decimal, `0x` hexadecimal and leading-zero octal. Invalid octal such as `08` is rejected. Floating constants use `0fXXXXXXXX` bit notation. This is narrower than full PTX syntax.

## Instructions

| Family | Accepted spellings |
| --- | --- |
| Parameters | `ld.param.u32`, `ld.param.u64`, `ld.param.f32`, matching the parameter type |
| Global memory | `ld.global.f32`, `st.global.f32`; 64-bit address with optional nonnegative 4-byte-aligned byte offset |
| Move/address | `mov.u32`, `mov.b32`, `mov.u64`, `mov.b64`, `mov.f32`, `cvta.to.global.u64` |
| Integer arithmetic | `add.u32`, `add.u64`, `sub.u32`, `mul.lo.u32`, `mul.wide.u32`, `mad.lo.u32`, `div.u32`, `rem.u32` |
| Signed arithmetic | `add.s64`, `mad.lo.s32` (modular result bits); `mul.wide.s32` sign-extends both operands before a 64-bit product |
| Floating arithmetic | `add.f32`, `mul.f32`, `sub.f32`, optionally with `.rn` before `.f32`; separate operations carry SPIR-V NoContraction |
| Predicates/select | `setp.ge.u32`, `setp.lt.u32`, `setp.eq.u32`, `setp.lt.f32`, `setp.ge.f32`, `selp.f32` |
| Additional predicates | `setp.ge.s32`, `setp.lt.s32`, `setp.eq.u64` |
| Control flow | labels, `bra`, `@%predicate bra`, `@!%predicate bra`, `ret` |
| Special registers | `%tid.x`, `%ntid.x`, `%ctaid.x`, `%nctaid.x` |

Unknown directives/modifiers, unsupported predication and mismatched types are rejected. Signed operations interpret existing 32/64-bit register contents; separate signed register declarations and negative-token immediates are not added. Synthetic signed tests use hexadecimal two's-complement bits. Other signed arithmetic, division by zero, NaNs, infinities, denormals and uncommon rounding behavior remain outside the validated workload. Finite test inputs do not establish full PTX floating-point conformance.

## Launch and trust boundary

Launches are synchronous and one-dimensional: Y/Z grid/block dimensions must be 1; X must be positive and within device limits. Streams, dynamic shared memory and packed `extra` arguments are unsupported. `kernelParams` points to host storage of 8 bytes per device pointer and 4 bytes per scalar.

Pointer arguments require 4-byte alignment and at least 4 bytes in a current-context allocation. This cannot prove the extent of subsequent kernel accesses. Callers must provide valid extents, initialized inputs and terminating trusted code. CT is not an isolation boundary for untrusted PTX. Arbitrary C host pointers must also be valid and sufficiently sized.

Module/function handles belong to their creating context. Unload invalidates its functions; context destruction invalidates all owned handles. Uncertain native completion or cleanup poisons the context and retains possibly live resources until process exit.

PTX source is not retained as module metadata or written to logs. No translated binary cache is published. Cubins, general nvcc output, cudart, CUDA libraries, atomics, shared memory and warp semantics are unsupported. M3d adds a bounded [raw fatbin profile](fatbin-profile.md) containing one uncompressed PTX module, while historical ASCII PTX under a `.fatbin` filename remains supported. See [M3c results](../M3c-RESULTS.md) and [M3d results](../M3d-RESULTS.md).

References: [PTX 7.0](https://docs.nvidia.com/cuda/archive/11.0/parallel-thread-execution/index.html), [SPIR-V registry](https://registry.khronos.org/SPIR-V/), [Level Zero specification](https://oneapi-src.github.io/level-zero-spec/level-zero/latest/).
