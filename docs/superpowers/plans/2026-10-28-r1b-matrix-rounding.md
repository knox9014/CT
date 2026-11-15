# R1b Matrix Rounding Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans, TDD, one independent read-only review and fresh source-bound validation. Preserve protected11 and original index/HEAD. No root stage/commit/push.

**Goal:** Qualify rounding-sensitive original matrix PTX with an exact sequential FMA oracle and an independently checked real-dot error budget.

**Architecture/design:** Keep baseline/R1a contracts intact. Add a closed rounding contract (schema3, explicit worker flag), reuse the same original PTX worker/observation gate, and bind a fresh R1a parent capture. Test strict per-FMA RN-even output semantics separately from high-precision real-dot accuracy. User delegated implementation choices; this selects a bounded first numerical extension, not broad floating-point or complete R1 qualification.

**Tech Stack:** Python integer IEEE oracle already in fma_check.py, Fraction-based independent rounding/cross-check, existing Rust Driver/SPIR-V/Intel path.

## Contract fixed before execution

- Cases(tile,M,K,N): (16,16,16,16),(32,32,64,32). Full tiles; max1024 threads; at most two jobs/worker,60s child timeout. Pinned original PTX ascending-K FMA chain remains unchanged.
- Seeds193,194,295,296. Even seeds generate signed nonuniform decimal-ratio inputs requiring binary32 conversion and accumulation rounding. Odd seeds use the fused-residual discriminator: start with -s, then FMA(s*(1+2^-23),1-2^-23,-s), yielding -s*2^-46; remaining products are zero, with seed-dependent inactive input values. Signs vary by row/column. Two instances each; these are converted binary32 inputs, not exact real decimal arithmetic.
- Sequential semantics: fma_check.fused_bits at each K step from +0, 0ULP tolerance, exact zero sign, finite outputs. Fraction rounding cross-check uses host float only to locate candidates, then exact rational distance and tie-to-even selection; bounded normal/zero intermediates, no overflow/subnormal qualification here.
- Real-dot accuracy: exact sum of binary32 input Fractions. For each cell, absolute error <= gamma_K * sum(abs(A_j*B_j)), u=2^-24, gamma_K=K*u/(1-K*u). No relative-only check and no post-hoc tolerance. This real-dot bound does not replace the strict FMA bit check.
- Four positive seeds x two cases=8 combinations/5120 outputs per pass. Four omission observations(two seeds each for no-launch/no-copy)=8 negative jobs. Require every input/output/guard; NaN, infinity, single-bit corruption, split-FMA zero, wrong profile/schema/command, identity drift must fail.
- Capture and separate deterministic replay pin source/provider/profile/job/raw output hashes. Existing app/R1a evidence remains separate. Long lifetime/concurrency, extra EXE shapes and whole R1 remain unfinished.

## Tasks

- [x] Red/green tests for independent rational rounding anchors, seeded binary32 recipes, selected complete sequential Fraction dots, FMA-vs-split discrimination, real-dot budgets and corruption refusal. Implement matrix_rounding_check.py.
- [x] Red/green worker/observation tests; add closed --rounding-v1/schema3 dispatch with explicit identity mapping. Preserve baseline/breadth flags and schemas.
- [x] Implement run_matrix_rounding.py with fresh R1a parent, exact scope/case set, source/artifact binding, audit and replay. Test scope/ULP drift and missing/relabelled observations.
- [x] Independent review, clean checkpoint CPU lane, freeze source, fresh Intel parent+rounding capture/replay. Privacy/protected11/index verification and result/plan records. Do not mark whole R1 complete.

Completed2026-10-28: [R1b results](../../R1B-MATRIX-ROUNDING-RESULTS.md). Clean CPU11/11, Python252, Rust207/4ignored, Runtime129. Fresh parent capture and8 rounding combinations/5120 exact FMA outputs,8 omission jobs, separate deterministic replay passed at cdf9140 scope. Real-dot Fraction bounds also passed without tolerance changes. WholeR1 remains unfinished.
