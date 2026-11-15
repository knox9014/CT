# Original matrixMul blocker triage and read-only loader diagnostics

> **For agentic workers:** Use superpowers:executing-plans and test-driven-development, followed by independent review.

**Goal:** Build pinned original NVIDIA matrixMul, identify its actual first CT connection barrier, and expose missing CUDA imports without weakening execution checks.

**Design:** Keep default `inspect_pe` strict. Add explicit diagnostic mode which reports missing named Driver/Runtime imports, `compatibility:blocked` and execution_performed:false after all existing PE validation. CLI `ct inspect --runtime --diagnostic` opts into the exact Runtime12 map and read-only reporting. `run`/`prepare_bundle` never use diagnostic mode and must still reject missing symbols before staging/execution. No fake CUDA capabilities, event timing, pinned memory or sync aliases are introduced.

**Upstream:** NVIDIA/cuda-samples commit `2b689228b746248b7bb7d2778d5ea0701669f7d3`, matrixMul.cu blob `98c4184c94b3edc02e4ecd60a62c7056955e741b`, SHA256 `ac470baa613a391e90f148c064cc60320395419995beb3b0e8ad8ba43bdfa8bb`. Canonical source and six Common headers stay ignored and unmodified. Use authenticated nvcc12, shared cudart/default device-runtime registration, PTX8/sm52 and existing diagnostic host override: upstream_adjusted_build.

## Tasks

- [x] Add failing CLI and parser tests for missing-name reports, supported-but-unproven status, structural rejection and strict bundle/run denial.
- [x] Implement diagnostic-only collection and CLI flags. Preserve strict defaults and malformed PE checks.
- [x] Compile actual unmodified matrixMul; capture source/tool/recipe/artifact hashes, actual PE imports and strict CT run rejection. Do not launch unsupported kernels.
- [x] Separately inspect real compiled PTX with actual translator, record rejection and semantic requirements as offline evidence, not reached execution.
- [x] Replay diagnostic inspections and compatible external vectorAdd regression with current code; CPU checks, independent review and privacy checks; record dependency-based next implementation scope.

## Limits

Loader failure is distinct from later source/PTX requirements. A successful diagnostic command means inspection succeeded, not app compatibility. Do not call all missing imports the first runtime-called function. The next implementation plan must honor capability truthfulness, submission lifetime and synchronization semantics rather than adding nominal success stubs. Preserve all11 user-owned files and historical acceptance checkouts.

Completed 2026-10-26. See [results](../../MATRIXMUL-TRIAGE-RESULTS.md). Ruling: use a separately pinned official profiler header archive instead of editing original source or the base toolchain. Ruling: follow the actual module exporter protocol (unsupported exit3, line/category fields); record-only script failures do not count as app/kernel execution. Recheck normalizes relative paths, preserves original records and validates full derived evidence. Next work is the device-query/host-memory/submission dependency frontier, not success stubs.
