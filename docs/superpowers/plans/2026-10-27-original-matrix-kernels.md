# Original Matrix Kernels Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans with independent read-only review.

**Goal:** Execute both pinned original matrixMul kernels on Intel with bounded exact data and inspect all results.
**Architecture:** Preserve the complete genuine PTX module, call original five-argument entries via the CT Driver in an isolated worker, and independently verify raw readbacks in the parent. Use existing forwarding DLL omission controls.
**Tech Stack:** Python ctypes/subprocess, CT Rust Driver/Intel backend, pinned nvcc source/producer, actual SPIR-V validator.
**Spec:** Continue the approved small-input original-kernel milestone; user delegated routine implementation choices. This does not run the original matrixMul EXE.

## Closed scope

Original C,A,B,wA,wB ABI, with wA=K/wB=N; row-major output MxN from A[M,K]*B[K,N].
Cases (tile,M,K,N): (16,16,16,16), (16,32,48,64), (32,32,32,32), (32,64,64,96).
Blocks tile×tile×1, grids N/tile×M/tile×1; inner iterations1/3/1/2. Query native
attributes1..7 before launch and reject unsupported1024-thread groups. No partial
tiles, zero/negative dimensions, arbitrary user PTX or unbounded loops.

Use integer coefficients A[-8,8]/8 and B[-9,9]/16. Integer dot products divided
by128 and every intermediate F32 sum are exact at these bounds. Compare all
9472 output words per seed bit-for-bit, all A/B bits unchanged, and16-word guards
on both ends of all three buffers. C initially contains NaNs. Use two seeds.

Worker validates closed job schema, file extents/hashes/entry set before loading
the explicit local DLL, then loads the unedited original module, supplies all
five parameter storage pointers, launches synchronously, explicitly synchronizes
context and writes raw readbacks. Close module/allocations/context and report
API completion only; numerical acceptance happens in the parent.

Same worker and job data run against CT, existing host-noop.dll and copy-noop.dll
with the genuine CT underlying DLL. Do not give worker an expected mode or any
CPU-generated result to upload. Omission controls may return API success but must
fail the parent's numerical check. Hash inputs/providers before and after. Never
submit invalid/divergent kernels. Child timeout60s; stop on timeout rather than
retrying a potentially incomplete GPU execution.

Alternatives: running the original EXE now would conflate device-selection policy
and lengthy app defaults; rewriting kernels would lose original-code evidence.
Choose a bounded Driver consumer of unchanged original PTX. This is kernel-only
evidence, not original-app execution, CUDA framework support or performance.

Ruling: use unequal K/N in the multi-tile case for each entry, so a swapped wA/wB
ABI cannot hide behind square dimensions. Preflight all four cases before the
first launch; preserve original errors alongside cleanup failures and report
success only after complete context cleanup.

Ruling: bind the worker to the known raw original PTX hash, not just entry names.
Initialize each GPU buffer to NaN words using real cuMemsetD32 before HtoD copies.
Then no-copy cannot accidentally reuse stale correct input values; verify its A/B
readbacks remain the poison pattern. No-launch must preserve uploaded A/B and
initial C exactly. The worker computes input recipes, not expected dot products.

## Tasks

- [x] TDD exact integer-dot/guards/NaN false-pass and strict geometry/job checks.
- [x] Implement closed Python worker and exploratory original16/32 entry execution.
- [x] Independent review, source-bound capture linked to fresh FMA parent/vectorAdd/schema3 matrix triage and actual validator; positive2seeds and omission controls, raw buffers and replay audit.
- [x] Full Python/Rust/Runtime checks, strict format/clippy, privacy/user11 preservation, source-bound results and next app/device policy scope. No staging/commit/upload; private artifacts ignored.


## Execution ledger

Frozen capture and replay pass for both original entries, four closed geometries,
two positive seeds, full9472 output words per seed and all input/guard bytes.
Both omission controls complete APIs and cleanup but fail all numeric cases with
the required buffer signatures. Source/worker/builder independent reviews found
no concrete blocker. Python215, workspace195 (4 existing ignored), Runtime129,
strict clippy and format checks pass. Original vectorAdd capture/replay and fresh
matrix triage/actual validator are hash-linked. The original EXE is never run.
Next: compute capability75/76 policy, explicit device selection, complete Runtime
path and externally verified app output. Full source/artifact identities and
limits: [results](../../ORIGINAL-MATRIX-KERNEL-RESULTS.md).
