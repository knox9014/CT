# Static Shared Memory Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task by task, with independent read-only review.

**Goal:** Execute bounded static CTA shared memory in genuine nvcc programs on Intel.
**Architecture:** Preserve shared symbols and address provenance separately from global memory. Lower each per-kernel object to an independent SPIR-V Workgroup array; shared addresses are relative byte offsets, never global physical pointers.
**Tech Stack:** Rust PTX parser/IR, SPIR-V1.0 Kernel/OpenCL1.2, Level Zero, Python/native CUDA diagnostic.
**Spec:** Scope and decisions below; user delegated implementation choices and requested continuing the shared-memory milestone.

## Scope and choices

Use per-kernel `.shared .align {4,8,16} .b8 name[N]` or 32-bit typed arrays,
at most16 objects and16384 padded bytes/kernel. Require one returning block even
if no barriers. Existing canonical bar.sync0 remains the only rendezvous form.
Support u32/b32/f32 loads/stores with exact-width registers and optional volatile.
Shared addresses may be32 or64 bits, derived by mov of a symbol, scalar addition,
and unsigned32->64 widening; cvta.to.shared only on proven shared addresses.
Prove4-byte alignment and retain exact object identity through register reuse.
Reject shared/global crossing, pointer escape, mixed objects, unsupported pointer
arithmetic, malformed/extern/dynamic/oversized declarations, and CFG before GPU.
Dynamic indexing bounds remain the CUDA program's responsibility; this is not
a memory sandbox. Reject statically known out-of-range direct accesses.

Approaches considered: physical Workgroup pointer integer casts would conflate
address spaces; direct-only accesses would miss actual nvcc shared-address shapes.
Choose symbolic object plus relative byte offsets, with conservative provenance.
No dynamic shared launch bytes, U64/vector/atomic shared accesses, CFG expansion,
matrixMul execution, AMD backend or performance claim in this slice.

## Tasks

- [x] Add parser/provenance rejection and SPIR-V Workgroup allocation tests; watch missing-feature failures.
- [x] Extend Kernel/Value and shared-specific IR, parse declarations and32/64-bit shared addresses, implement a bounded linear provenance/alignment validator callable by parser and emitter.
- [x] Lower distinct per-kernel Workgroup arrays, AccessChain and typed32-bit accesses, preserving volatile and exact barrier semantics; validate with pinned spirv-val.
- [x] Build genuine nvcc two-entry/two-array shared exchange fixture, verify all values/guards for64/128 threads and multiple blocks; use launch/copy omission controls, never execute malformed variants.
- [x] Independent review, compatibility docs, freeze source, native regression capture, full Rust/Runtime/Python checks, fresh vectorAdd capture/replay, matrixMul offline diagnosis.
- [x] Preserve user11 baseline, privacy scan and ignored local artifacts; write source-bound results. No staging/commit/upload.

## Execution notes

Independent review identified a scalar conversion retaining a pre-truncation
known value (4294967296 becomes0 at U32). Watched the parser regression fail,
then discarded scalar full-value knowledge across conversions, retaining only
low-bit facts. Added a mutated-public-IR regression. Re-review found no further
blocker. Unknown shared instruction modifiers are also explicitly rejected.

Frozen capture verifies1408 output values per seed across both types/modes,
two distinct seeds, guard/input preservation, omission controls, genuine PTX vs
fatbin identity, exact storage/barrier lowering and actual validator controls.
All199 Python tests,129 Runtime tests, workspace tests, strict clippy and format
checks pass. Fresh vectorAdd capture/replay pass. matrixMul remains blocked at
bra.uni line51 and is never executed. Full source/artifact identities and remaining
limits: [results](../../STATIC-SHARED-MEMORY-RESULTS.md).

References:
https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html
https://registry.khronos.org/SPIR-V/specs/unified1/SPIRV.html
