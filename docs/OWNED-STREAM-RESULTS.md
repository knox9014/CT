# Owned synchronous streams (2026-10-26)

Added cudaStreamCreateWithFlags and cudaStreamDestroy, connected created streams to compiler launch configuration, Runtime kernel execution and synchronization. Current diagnostic contract: Runtime30 / Driver39. This implements context-owned synchronous stream handles; no FIFO worker queue, independent native queues, async copy or overlap claim.

Flags0/1 accepted; null output/other flags1 with output preserved. Tokens never reuse (128live/4096lifetime). Stale/cross-context400, unknown/sentinel non-null801, null destroy400. Entry gates serialize use/close; registry locks are released before waiting. Close invalidates even if its completion callback fails. Ordinary callback errors permit retry;709 fails subsequent use; poisoned entries999 remain reserved. Internal callbacks must not nest stream gates. Destroy streams before externally destroying their context; external context destruction does not reclaim registry live slots yet. Current Driver context IDs do not reuse identities.

## Verification

- Runtime Rust94 passed; workspace tests passed (three pre-existing ignored). Runtime/workspace clippy and formatting passed; profile/compatibility/coverage static checks passed.
- Python185 passed after final source freeze.
- Real nvcc consumer launched an integer kernel through both flags0 and1 streams, checked32 complete outputs and two host guard words, synchronized/destroyed each, and rejected stale synchronization/repeated destruction400. Two fresh input seeds passed. The no-op launch provider returned data-failure42, detecting skipped execution.
- Official-header native controls passed: exact30 exports; actual GPU memory roundtrip/context preservation; missing Driver35; synthetic synchronize709. The709 control now also creates a named stream, fails its synchronization, destroys it with709, observes stale400 and creates/destroys a distinct replacement.
- Four existing default/kernel/symbol/u64 pure ABI consumers were rebuilt and passed against the same Runtime DLL. Attribute five-mode controls also passed as part of the fresh capture.
- Independent read-only review found a failed-stream destruction bug. Added destruction-specific preflight plus integrated live-limit-one regression; corrected path passed CPU and native709 controls. Final review found no additional blockers. Review itself did not execute tests.
- Original pinned upstream vectorAdd source unchanged: Runtime30 custom shared-cudart capture and replay passed original application, trace/no-op and independent raw-buffer checks.
- Original matrixMul rebuilt and inspected without execution. Missing Runtime imports11 to10 (stream creation now exported). PTX still rejects .shared line32; shared memory, barriers/FMA and compute-capability device selection remain separate blockers.
- Eleven pre-existing user-owned files preserved; publication scans passed. Raw captures/vendor binaries remain ignored/local; nothing uploaded.

## Local diagnostic evidence

Source fingerprint: `3373f4559b2b1f94a71df8b11cc13d5312cac887801723b6e9890c0aba6eef08`.

| Capture | Manifest | SHA-256 |
| --- | --- | --- |
| Owned stream kernels | `.cache/runtime-attribute-runs/ca4c94d24ea1465b88daf24f7cfd059d/owned-streams-manifest.json` | `4f42f5c554740ef310beaa9fca193d848219c728fc6263e1894795f4850dca56` |
| VectorAdd | `.cache/upstream-vectoradd-runs/4c96e15023164714ac6a404e26d92aa2/manifest.json` | `8b2c7a7526dd621ad841e6b69a557e47661caeafb2d54b8a95c30fc6e90b47e9` |
| MatrixMul offline | `.cache/matrixmul-triage/9d5da761b5204260bfe58e62c43cb01c/manifest.json` | `e2426b842ff40721715219ee99ec8d5e0a4562e3f26d44551b3f9b33744f4b9b` |

Native folder also includes stream-manifest.json, manifest.json (attribute checks) and existing-abi.json. Vector replay: replay-1b0f321c17014d0197ebda21df7c519f.json. Reproduce owned stream diagnostics with `python scripts/run_owned_streams.py` using the previously authenticated local producer cache. Source changes invalidate audit of these old captures; this is not clean-release evidence.

Next: genuine host allocation ownership/lifetimes before asynchronous submission, then events/profiler. Remaining matrixMul import names are cudaHostAlloc/cudaFreeHost, cudaMemcpyAsync, five event functions and cudaProfilerStart/Stop. Do not count these as implemented until the actual supported paths and controls pass.

[Dependency plan](superpowers/plans/2026-10-26-matrixmul-runtime-closure.md). [Previous default stream capture](DEFAULT-STREAM-SYNC-RESULTS.md) describes historical Runtime28.
