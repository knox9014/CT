# Access-specific U64 pointer alignment implementation plan

> **For agentic workers:** Use superpowers:executing-plans with test-driven-development and final independent source review.

**Goal:** Remove unrelated-pointer alignment rejection and support natural nvcc mixed-width pointer kernels while retaining a bounded proof for every U64 access.

**Spec:** [Research R1](../../CT-RESEARCH-AND-ROADMAP-REVIEW-2026-10-25.md). Scope is alignment/provenance, not bounds, ownership, arbitrary pointer arithmetic or CUDA conformance.

**Architecture:** New `ct-ptx/src/alignment.rs` performs forward CFG fixed-point analysis. Facts carry unique pointer-parameter origin / scalar / unknown and possible residues modulo8. Param loads, mov/cvta, same-width64 conversion, pointer+scalar/pointer-scalar, scalar arithmetic and literal left shifts have conservative transfer rules. Unknown stays distinct from scalar. Joins union residues and retain origin only when identical. Unreached states remain separate; entry has a virtual unknown boundary even with a backedge. Validate each U64 memory instruction's pre-state only after convergence; retain immediate offset checks. Reject budget exhaustion (4096 block visits). Named typed globals are exempt.

Validated inferred `.param.u64` pointers are candidate align8 roots; after proof promote exactly the roots used by U64 accesses. Existing launch validation then checks their alignment and minimum8-byte extent. Explicit align4 roots are not promoted. Unrelated and narrow-only inferred pointers remain align4. No API export change or silent backend fallback.

## Steps

- [x] Add tests that fail on current global gate: mixed alignment, selective inferred promotion. Add negative dynamic offsets/clobbers, branch/loop joins and forged addresses.
- [x] Implement bounded analysis and replace old global gate. Run parser/codegen regressions and explicit inferred ABI metadata tests.
- [x] Add native/genuine producer regression with a narrow pointer at4mod8 and an aligned wide output; verify guards/results, inferred wide pointer rejection at4mod8, no launch on invalid inputs, and unchanged narrow-only contract.
- [x] Run Rust/Runtime/Python, actual spirv-val and native checks; independent review and privacy scan; record actual scope, not-run and retained historical evidence.

## Files and decisions

`crates/ct-ptx/src/alignment.rs`, `parser.rs`, `lib.rs`: analysis integration. `crates/ct-ptx/tests/alignment.rs`: joins/loops/negative cases. Native fixtures/harness and codegen tests bind selective promotion to actual consumer behavior. Tests inspect declared parameter alignment as well as parse success.

Ruling: use a conservative bounded proof rather than removing validation or requiring every pointer align8. Distinct pointer roots at joins and unsupported address operations may reject valid PTX until separately implemented. Ruling: existing user files and accepted worktrees remain untouched; use fresh ignored build directories.

Completed 2026-10-26. See [results](../../POINTER-ALIGNMENT-RESULTS.md). Ruling: migrate the old immediate test from scalar-as-address to named global, preserving literal coverage under stricter wide-address proof. Final verification uses a fresh source-bound capture after fmt/profile updates; the earlier exploratory capture is not current evidence.
