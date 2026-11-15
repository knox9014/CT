# R1c Bounded Resource Lifetime Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans, TDD, one independent read-only review and fresh source-bound native/CPU validation. No root stage/commit/push; preserve protected11/index/HEAD.

**Goal:** Exercise repeated Runtime resource reuse and separate Driver module retirement, including recoverable errors and native live-budget recovery.

**Architecture/design:** A genuine nvcc Runtime consumer performs API checks and emits raw full-buffer results; Python independently judges numerics. A separate ctypes Driver worker loads/unloads a synthetic vector PTX module repeatedly, returns raw buffers and rejects stale functions/modules. Never mix these contexts. Fresh R1b parent capture pins current providers/tools and existing application/numerical regressions.

**Tech Stack:** Existing Rust Runtime/Driver, nvcc/MSVC diagnostic build, Python/ctypes/std::vector consumers and exact integer/float-bit oracles.

## Closed scope fixed before execution

- Seeds193,731. Positive Runtime workers256 cycles, Driver workers160 cycles. Omission controls8 cycles each. One worker thread/process,180s timeout; no hours-long soak or concurrency claim.
- Runtime cycle: two pinned host allocations, two device allocations, one owned stream(flag0/1), one re-recorded event; async H2D, source-host free immediately after enqueue and before explicit sync, kernel, full A/B async D2H and three completion paths(event wait/stream destroy/device free). Every input/output word and device/host destination guard is observed; raw row70 u32 words contains2 host+4 device guard words.
- Recoverable invalid stream flags1, pageable async copy801 and immediate duplicate host/device free1 each cycle. Destroyed stream/event sync/destroy must return400; first tokens remain stale after replacements. Do not assert stale raw allocation pointers after address reuse.
- Runtime stream/event native live boundaries128: creation129 returns801, release all, create/destroy replacement successfully. Total tokens stay below4096 lifetime limits. These checks are not proof of zero hidden memory/RSS leaks.
- Separate Driver worker160 times loads fixed synthetic vector PTX, performs failed-name lookup500, correct launch, reads/preserves all A/B/C and16-word guards each side, unloads, rejects stale launch/lookup and duplicate unload400, frees device storage and rejects immediate duplicate free1. All outputs are exact small dyadic f32 words.
- Positive runs each use both seeds; no-launch/no-copy controls use one seed each. A separate no-unload provider must fail duplicate-unload validation with controlled exit42 before any success claim. Process context cleanup runs on the rejection path.
- Nine closed observations: Runtime4, Driver4, Driver no-unload1. Raw outputs required even when consumers report API completion. Capture/replay bind command/profile/source/parent/provider/input/output hashes, requiring deterministic observations. No timing/performance assertion.
- Single-thread recoverable-error cleanup only. Actual device loss, concurrent host calls, default/Driver stream interop, reset, dynamic Runtime registration unload and whole R1 remain unfinished.

## Tasks

- [x] Red/green independent Runtime/Driver raw oracle and schema tests: cycles, completion modes, counters, every final word/guard, omission signatures, stale/error/quota metadata and fake completion refusal. Implement lifecycle_check.py.
- [x] Implement nvcc lifecycle_runtime.cu and separate lifecycle_driver_worker.py with bounded profiles/cleanup. Test fail-closed CLI/job construction; add lifecycle_no_unload.c control.
- [x] Implement run_resource_lifetime.py with fresh R1b parent, compiled native producer, pinned PTX/commands/files, nine observations, audit/replay. Test scope/case/source/provider drift and missing observations.
- [x] Independent review; clean CPU checkpoint; freeze source and run fresh Intel capture/replay. Record bounded result and privacy/protected invariants, leaving whole R1 and concurrency unqualified.

Review ruling: immediate free-before-explicit-sync is coverage, not proof the job was still pending. Blocking-path proof remains in deterministic controlled Rust tests; no native overlap/blocking-duration claim is made.

Completed2026-10-28: [R1c results](../../R1C-RESOURCE-LIFETIME-RESULTS.md). Clean CPU11/11, Python262, Rust207/4ignored, Runtime129. Full current-source parent capture and9 lifetime observations/separate replay passed at d28b4fe2 scope:512 Runtime and320 Driver cycles;5 controls detected. Integrated completion sequences include a final event synchronization before raw inspection, so no isolated native-fence timing proof is claimed. WholeR1 remains unfinished.
