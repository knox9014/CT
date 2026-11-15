# R2b bootstrap resolver correction plan

> **For agentic workers:** Use superpowers:executing-plans with TDD and one independent final review.

**Goal:** Correct verified bootstrap lookup modes/ranges without inventing a supported Driver version.

**Architecture:** Add explicit per-entry permission for legacy fallback on stream-insensitive functions. Only cuInit, cuDriverGetVersion, cuDeviceGetCount and cuGetProcAddress self-lookup receive audited request support through12090. All other request ceilings and unsupported PTDS/PTSZ modes stay bounded. Separately preserve native12.9 Runtime/CuPy version/prefix observations.

**Tech stack:** Rust existing Driver, CPU/native resolver tests, Python diagnostic workers and official CUDA12.9.79 Runtime/header archive.

**Spec:** `2026-10-28-r2b-static-runtime-contract.md`; independent read-only review of official12.0/12.9 typedefs and resolver semantics.

## Contract

- cuInit_v2000, cuDriverGetVersion_v2020 and cuDeviceGetCount_v2000 signatures remain unchanged in the pinned12.9 headers. For those names, requested versions through12090 and flags0/1/2 select the same real CT function.
- Self-lookup continues selecting the four-argument resolver at11030..11999 and the five-argument resolver at12000..12090. flags2 is safe because the resolver has no per-thread-stream variant.
- This is a request/ABI ceiling, not a supported CUDA-driver version. cuDriverGetVersion remains801/output0, including when called through new lookup paths. Null output remains invalid1. No initialization or virtual-target-policy latch occurs during lookup.
- Non-audited names retain the12000 ceiling and flags2 rejection801. In particular copies, memsets, event record and launch must never acquire fake PTDS parity. cuCtxCreate's11040 ABI transition remains blocked.
- Old resolver missing-symbol behavior500/null and new resolver0/null/status are preserved. Invalid arguments and version>12090 initialize outputs and reject. No new exported symbol or GPU feature claim.
- Native12.9 version/prefix probes are isolated and use only version/device-count functions, never kernels. Observed probes are diagnostic, nominal probes remain separate. The dynamic12.9.79 Runtime comparator is not proof of CuPy's exact static patch build.
- Preserve protected11/root HEAD/index and user changes. Use ignored local artifacts and no stage/commit/push/upload. Work in the authorized ongoing root; accepted worktrees stay untouched.

## Tasks

- [x] Add failing Rust tests for all four audited names at floors/12000/12090, flags2 pointer identity and recursive ABI calls, actual version-query errors, non-audited/transition/unknown/invalid boundary rejection and threaded lookups.
- [x] Implement explicit per-entry fallback/range policy; update only the corresponding four profile lookup ranges and public lookup documentation.
- [x] Add failing Python tests and implement deterministic bootstrap trace classification/version-probe checking; allow explicitly opted-in native DLL observation while retaining the default CuPy-only extension rule.
- [x] Run the unmodified CuPy static version query and official12.9.79 Runtime nominal/observed version/null/device-count probes in fresh children. Build a fresh CT Driver, verify archive/package/provider/module bytes and source identity, preserve captures and recheck.
- [x] Run official12.9 header ABI checks for the four selected functions; run existing Rust/Runtime/Python/registry checks, independent review, privacy/protected checks, record results and remaining version blocker.

## Rulings

- Keep numeric Driver version unsupported. Existing virtual compute target only controls PTX selection and cannot authorize a new Driver-version claim, especially before cuInit policy selection.
- Extend four audited names only; do not broaden every46 entries from a header version label. This corrects common caller bootstrap lookups while the CuPy version-call blocker intentionally remains visible.
- Completed bounded correction: all five resolver tests pass, compile-only12.9 ABI proof passes, seven generation-matched native/version children and five original CuPy-task children meet their diagnostic contracts. Both saved-capture rechecks pass. Clean source CPU11/11, Python281, Rust209/4 existing ignored, Runtime129 pass. See `docs/R2B-BOOTSTRAP-RESOLVER-RESULTS.md`; whole R2/common initialization/version support remains open.
