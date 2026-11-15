# Uniform Control Flow Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans, with independent read-only review.

**Goal:** Execute bounded CTA-uniform branches and loops with shared memory/barriers on Intel.
**Architecture:** Prove every conditional branch CTA-uniform at a fixed point, then validate shared provenance/alignment at converged CFG states. Treat bra.uni as a hint, never proof.
**Tech Stack:** Rust PTX/IR, SPIR-V1.0 Kernel/OpenCL1.2, native nvcc/Intel diagnostics, Python oracle.
**Spec:** User delegated implementation choices and requested continuing the shared/control-flow milestone. Scope below is the implementation decision.

## Contract

Constants, kernel parameter values and nctaid/ntid/ctaid builtins are CTA-uniform;
tid and every memory load result are varying. Compute is uniform only if every
input is uniform. All conditional branches in a shared/barrier kernel must have
uniform predicates after a bounded must fixed point. Joins AND uniform facts;
entry input stays nonuniform even with backedges. Existing definite assignment
and target/reachability/type/resource validation precede proof. Reject partial
proof on4096 block visits or65536 interpreted instructions. Trusted program
termination and valid memory bounds remain caller responsibilities.

Shared facts join exact origins only when identical, union possible residues,
retain known values only when equal, and OR an independent may_shared taint.
Ambiguous roots cannot be shared access bases. Any possible shared address is
forbidden in escape/global-memory/unsupported arithmetic consumers. Unreachable
input is separate from unknown data. Analyze to convergence before final memory
validation and root collection; emitter repeats proof for public IR.

Keep static16-object/16KiB shared limits and32-bit accesses; no general divergent
barriers, warp/cluster/dynamic shared, fused arithmetic, or matrixMul execution
claim. Preserve ordinary barrier-free/shared-free CFG behavior. Parse predicated
and unconditional bra.uni with the same semantics as bra and prove it independently.

Alternatives: trusting .uni admits false hints; general convergence/reconvergence
analysis is a larger separate feature. Choose whole-CFG CTA-uniform control,
including uniform loops, to support useful iteration without accepting divergence.

## Tasks

- [x] Failing parser/proof tests for uniform diamonds/loop-carried values and rejected divergence, ambiguous roots, escapes, residue joins, budget exhaustion and mutated IR.
- [x] Implement bounded uniform proof, bra.uni parsing and CFG shared fact convergence; reuse existing emitter CFG lowering and revalidate before emission.
- [x] Genuine nvcc shared integer/F32 iterative kernels, zero/3/5 iteration paths,64/128 threads and multiple blocks, independent values/guards and omission controls; pinned actual validator and offline mutations/rejections.
- [x] Independent review, compatibility contract update then source freeze; full Rust/Runtime/Python checks and native parent regressions, fresh vectorAdd capture/replay, original matrixMul offline triage.
- [x] Preserve user11 baseline/privacy/ignored local artifacts; source-bound result document. No staging/commit/upload.

Ruling from independent design review: origin equality alone is insufficient at
CFG joins because Other would erase possible shared pointers. Add may_shared OR
taint and reject forbidden consumers on that taint, even without one must-root.

Ruling: require a possible Return path from every block, while leaving actual
runtime termination to trusted callers. Closed no-exit CFG components reject;
the native diagnostic uses only finite host-selected iteration counts0/3/5.

Ruling: genuine nvcc with the source's unroll1 hint emits the exact nounroll
pragma. Parse only that metadata spelling without treating it as a control-flow
proof or promising native compiler unrolling behavior. Existing blanket-CFG
negative fixtures now use genuinely varying branch predicates or invalid targets;
uniform jumps are valid in the new profile.

Ruling: intermediate shared transfer errors widen definitions to Other with
may_shared taint. They cannot produce accepted access roots. Final strict replay
uses converged states and is counted in the instruction budget. Public-IR
revalidation checks these convergence/provenance contracts; it is not a complete
instruction arity/type verifier for arbitrary hand-constructed IR.

Implementation and first native exploration passed independent review. A second
fresh source review also found no concrete blocker; neither reviewer ran builds,
tests or GPU work. Frozen captures remain separate evidence.

## Execution ledger

Frozen native capture passes two seeds,832 values per type/seed across0/3/5 rounds,
guards/input preservation and launch/copy omission controls. Genuine producer
fatbin correspondence, actual validator positive/undefined-target negative and
offline erased-loop/control rejection checks pass. Prior native parent regressions
are captured from the same source. Rust workspace192 (4 ignored), Runtime129,
Python201 tests and strict clippy/format checks pass. Fresh vectorAdd capture and
same-binary replay pass. Original matrixMul remains unexecuted; first parser
rejection is now fma.rn.f32 line86, so complete matrixMul control proof is pending
that parsing dependency. Next slice: fused arithmetic semantics/numerics, then
remaining application/device policy checks. Source-bound records and limits:
[results](../../UNIFORM-CONTROL-FLOW-RESULTS.md).

References:
https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html
https://registry.khronos.org/SPIR-V/specs/unified1/SPIRV.html
