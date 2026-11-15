# Pinned upstream Runtime vectorAdd verification plan

> **For agentic workers:** Use superpowers:executing-plans with test-driven-development and final independent review.

**Goal:** Execute NVIDIA CUDA Samples Runtime vectorAdd with original host/kernel source and unchanged generated EXE through CT, and independently check actual Runtime-path data.

**Upstream:** `NVIDIA/cuda-samples` commit `2b689228b746248b7bb7d2778d5ea0701669f7d3`, source blob `284b0f0e332f022ed6789456182238fc2fc6af54`, SHA256 `9a156c7c4f1ab0759d859af95c8dab55f2280d867edca7daee4546d63effb583`. Original source remains ignored, with original notices. Common headers come from pinned Git blobs. No vendor code is committed.

**Architecture:** Authenticated nvcc12/MSVC diagnostic recipe uses shared cudart, PTX8/sm52 and default device-runtime registration. This is upstream_adjusted_build, not original build recipe/distributed binary or supported-host qualification. Run nominal original DLL pair and a forwarding observational Driver provider capturing actual HtoD/DtoH bytes and launch parameters. Initialize unspecified allocations to NaN to expose missing writes. A launch-noop control deliberately demonstrates that upstream's fabs-based check can falsely accept NaN; CT's independent finite/float32 oracle must reject it. Keep observer distinct from nominal product DLLs. Replay identical bytes in new processes, without claiming new random inputs (upstream does not seed rand). Also execute actual producer PTX with independent guarded Driver inputs.

## Tasks

- [x] Add failing numerical/NaN/closed-schema observer tests, then implement independent oracle.
- [x] Build unmodified pinned source and original Common headers; validate source/blob hashes and PTX/fatbin/EXE identity.
- [x] Add observational forwarding provider, nominal/trace/noop controls, fresh-process replay and source/artifact audits.
- [x] Run external consumer and independent numerical inputs, actual validator and appropriate regressions; source review and privacy scan.
- [x] Record exact external app scope and next failure, preserve historical results. Keep historical application registry separate until immutable artifact acceptance; diagnostic results alone do not silently relabel old entries.

## Evidence boundaries

No source edits, inline assembly, EXE/PTX patching, CPU fallback, performance, NVIDIA parity, AMD, framework, static cudart or clean52-case acceptance claim. Existing user-owned files and accepted worktrees remain unchanged. Raw arrays, binaries, tool paths and manifests stay ignored. Actual observer data belongs to this synthetic-input sample, not arbitrary user programs.

Completed 2026-10-26; see [external diagnostic results](../../UPSTREAM-VECTORADD-RESULTS.md). Ruling: retain the historical registry unchanged until immutable artifact acceptance; this diagnostic has its own source-bound manifest. Ruling: sample PASS text alone is insufficient because the intentional NaN/noop control also prints it; require independent finite exact outputs and trace counters. Reviewer findings were reproduced and fixed before final capture.
