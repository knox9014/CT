# R1a Exact Matrix Breadth Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans, TDD and independent read-only review. Preserve the existing baseline and protected11 files; no root stage/commit/push.

**Goal:** Extend unchanged original matrix PTX execution to seven bounded geometries and three exact input recipes, without claiming a new general CUDA feature.

**Architecture:** Keep baseline contracts unchanged. A separate closed breadth contract selects seven full-tile jobs and three seed-dependent input patterns. The existing Driver worker and observation verifier receive an explicit closed contract; the worker accepts only the known breadth flag. A separate capture/replay script binds fresh parent application evidence and source/artifact identities.

**Tech Stack:** Existing Python/native Driver consumer, pinned original PTX and SPIR-V validator, Intel Arc, integer/Fraction CPU oracle.

**Spec/design:** R1 in intel-qualification-next.md. User delegated implementation decisions. Selected exact dyadic extension first because it isolates translation/indexing/accumulation mistakes from floating-point tolerance. Broader EXE shapes, non-dyadic FMA error budgets and resource lifetime are separate unfinished R1 work.

## Closed design

- Baseline four cases plus(tile,M,K,N)=(32,32,96,64),(32,96,32,64),(32,64,128,32). Full tiles only. Dimensions<=128, max1024 threads, max7 jobs/worker,60s child timeout.
- Six fixed seeds193,194,195,296,297,298: two instances each of mixed, asymmetric and pair-cancellation inputs. Recipe selected by seed modulo3; scalar integer coefficients bounded by9. A=integer/8, B=integer/16. Dot/FMA intermediates are integers/128 with absolute numerator<=128*81=10368, exactly representable in FP32. CPU integer-dot references are independently checked with Fraction tests.
- All A/B/C readbacks and16-word guards on each side must match; C starts NaN. Two controls each for no-launch/no-copy must complete API calls but fail numerical acceptance with the expected omission signature. Single-word/input/guard corruption must fail CPU tests.
- New job schema2 identifies breadth; original schema1/worker CLI/capture schema remain unchanged. Strictly closed geometry and pinned PTX entry identities; no arbitrary module/profile loading.
- Fresh parent virtual-target application capture proves current existing-app behavior separately. Breadth is a Driver consumer of unchanged original PTX, not a modified-input original EXE claim.
- Replay reexecutes the same six seeds and controls in fresh processes and requires identical observation hashes. Raw logs/binaries stay ignored.

## Tasks

- [x] Write failing breadth tests for closed geometry/limits, recipes and independent exact oracle, corrupted readbacks and schema rejection. Implement scripts/matrix_breadth_check.py.
- [x] Add explicit breadth contract to scripts/matrix_kernel_worker.py and reusable observation functions in run_matrix_kernels.py; preserve baseline behavior. Test exact breadth worker command and job binding with synthetic observations.
- [x] Implement scripts/run_matrix_breadth.py: fresh parent capture, exact source/provider/recipe identity,10 closed observations, audit and deterministic separate replay. Test incomplete/relabelled case sets and source/artifact drift rejection.
- [x] Independent review and relevant full Python/Rust checks; freeze source, fresh Intel capture/validator/numerics/controls/replay, privacy/protected11 verification. Record R1a result; do not mark whole R1 complete.

Completed2026-10-28: [R1a results](../../R1A-EXACT-MATRIX-BREADTH-RESULTS.md). Clean CPU11/11, Python242, Rust207/4ignored, Runtime129. Fresh parent application capture and breadth42 positive/28 omission jobs plus separate deterministic replay passed under frozenc0463862 scope. Whole R1 remains unfinished.
