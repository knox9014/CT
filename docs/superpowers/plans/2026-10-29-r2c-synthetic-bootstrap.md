# R2c isolated synthetic bootstrap peer plan

> **For agentic workers:** Use superpowers:executing-plans and TDD; independent design/final review required.

**Goal:** Identify which bootstrap calls a pinned Runtime attempts after controlled version responses, without changing CT's production version or claiming application compatibility.

**Architecture:** Build a separate Rust test-only DLL with no CT/backend linkage. It exposes only version/init/resolver/public export-table query functions plus test configuration/snapshot exports. Version modes are synthetic protocol inputs; cuInit and cuGetExportTable always reject. No device/allocation/copy/launch function address exists. Compare peers with identical surfaces across sample responses and tracing on/off. Keep real CT before/after baseline children separate.

**Tech stack:** Windows x64 Rust cdylib/test binary, Python ctypes, pinned official Runtime12.9.79 and headers.

**Spec:** This separate experimental contract; R2b's faithful CT forwarding/nominal classifiers are unchanged.

## Ruling and evidence limits

Prior plans' ban on version spoofing remains binding for product behavior and nominal qualification. It does not prohibit an explicitly synthetic protocol peer used solely as a controlled input. The peer is never linked to CT, never installed as a system driver, never used by the CuPy qualification command and never counted as application support. Production cuDriverGetVersion stays801/output0. The user delegated routine implementation choices and local testing; no new publication or machine changes are authorized.

An independent read-only design review endorsed this separation and required identical peer surfaces, real CT controls and narrow conclusions. Peers intentionally offer fewer functions than CT, so they are not pure version-only interventions relative to CT. Missing pointers may affect progression. Only comparisons among synthetic peers isolate the sample version response on that fixed fixture surface. Observed calls do not establish full mandatory dependencies, a truthful CT version or CUDA execution.

## Fixed protocol and guards

- Response modes:801/output0; success/output0; success/11000; success/12000; success/12090. Configure exactly once before the first lookup/call. No environment-driven or adaptive answer.
- Exactly five CUDA exports: cuInit, cuDriverGetVersion, cuGetProcAddress, cuGetProcAddress_v2 and cuGetExportTable. The latter's public signature is verified from pinned12.9 cudaTypedefs.h; it returns801/null and never fabricates private table contents or callable private pointers.
- cuInit(0) always records/rejects801; invalid flags reject1. Device, allocation, copy, kernel, stream and backend entrypoints are absent. Inspect the built DLL's export/import inventory and loaded paths/hashes.
- Both resolver ABIs use exact signatures and initialized output/status behavior, a fixed tiny surface, checked version/flag inputs and no pointer guesses for unknown APIs.
- Single-child/single-host-caller experiment; bounded512-row snapshots with overflow rejection. Trace requests and actual calls separately. Separate tracing-off children must match corresponding tracing-on result/exit without being relabelled nominal CT.
- Only Runtime device-count prefix calls, never allocation/launch. Unexpected device-count success or native fault stops the experiment and is not support evidence. No real NVIDIA fallback or CT forwarding.
- Raw vendor disassembly, packages, paths, tracebacks and captures stay ignored. No stage/commit/push/upload; protected11/root HEAD/index preserved. The ongoing root is the authorized workspace, accepted worktrees remain untouched.

## Files and tasks

- [x] Failing standalone Rust tests in `tests/bootstrap_peer.rs`, then implement the inert peer and its direct argument/output/configuration/lookup/snapshot contracts. Build with rustc, not a new Cargo workspace/member.
- [x] Add failing pure Python evidence tests, then `scripts/bootstrap_peer_check.py`, worker and runner for fixed cases, loaded-provider identity, before-child gates and saved recheck. No reuse of nominal CT acceptance for synthetic data.
- [x] Compile official-header ABI assertions for version/init/resolvers/public export-table signature. Run peer Rust tests and direct native fixture checks.
- [x] Run fixed traced/untraced peer cases and separate real CT before/after controls on the same pinned Runtime. Preserve requests vs calls and experimental confounds; stop on unexpected outcomes.
- [x] Independent final review, appropriate regressions, privacy/protected/index checks, report exact observed next call(s), and refine the actual initialization implementation plan without promoting synthetic success.

## Evidence ledger

All15 child expectations passed; tracing-off pairs matched, direct fixture ABI checks19 passed, standalone Rust4 passed. Real CT before/after remained801/version0 and Runtime35. Sample12000/12090 responses on the fixed peer surface reached cuInit, whose guard returned801; no device-count success or native fault. Clean source CPU11/11 passed, Python289, Rust209/4 existing ignored, Runtime129. See `docs/R2C-SYNTHETIC-BOOTSTRAP-RESULTS.md` and the separate R2d plan. Product version support and application compatibility remain unchanged.
