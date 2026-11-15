# Relaxed u32/b32 global memory operands Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Accept 64-bit register operands for 32-bit unsigned/bit global loads and stores without widening memory accesses.

**Architecture:** Keep the IR memory type distinct from the declared register type. Parser accepts exactly u32/b32 memory with U64 registers; emitter loads U32 then OpUConvert to U64, or reads U64 then OpUConvert to U32 before storing. Existing same-width operations remain unchanged. Signed widened loads, param/cvt relaxation, floating relaxation, pointer provenance changes and version APIs are separate work.

**Tech Stack:** Rust, PTX, SPIR-V Kernel/OpenCL, existing ctypes CUDA Driver harness.

**Spec:** [Research review R1](../../CT-RESEARCH-AND-ROADMAP-REVIEW-2026-10-25.md), [PTX 12.0.1 section 9.4.1](https://docs.nvidia.com/cuda/archive/12.0.1/parallel-thread-execution/index.html).

## Constraints

Preserve user-owned files, historical acceptance checkouts/results and existing pointer alignment restrictions. No claim of signed relaxation, general CUDA compatibility, new clean acceptance or original upstream app support. A hand-written regression matching a producer-observed instruction shape must be labeled as such.

## Steps

- [x] Add parser positives and negative width/type cases; confirm positives fail for missing support.
- [x] Add SPIR-V dataflow tests proving U32 memory loads/stores and explicit UConvert, not wider reads/writes; confirm failure.
- [x] Implement restricted parser acceptance and explicit code generation; migrate only obsolete width-rejection assertion.
- [x] Add guarded numerical Driver regression: zero/high-bit/all-one U32 loads overwrite poisoned U64, high bits of U64 stores are discarded, four-byte neighboring guards survive; named global and ordinary pointer paths.
- [x] Run Rust workspace and Runtime tests, pinned spirv-val, native regression if environment permits, fmt/clippy and publication/privacy checks. Record actual scope and any not-run.
- [x] Independent source review; fix actionable findings and update profile/results with remaining limits.

## Files

`crates/ct-ptx/src/parser.rs`, `crates/ct-ptx/tests/memory.rs`: operand acceptance. `crates/ct-codegen-spirv/src/emit.rs`, `crates/ct-codegen-spirv/tests/translation.rs`: type-preserving lowering. `tests/fixtures/relaxed_memory.ptx`, `tests/relaxed_memory_check.py`: synthetic numerical regression. `docs/compatibility/ptx-profile.md`: bounded support statement. Result document records verification rather than changing old P04c results.
