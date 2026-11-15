# Default-stream synchronization design and plan

Add cudaStreamSynchronize for the null/default stream as Runtime28. Driver39, bootstrap15 and kernel5 stay unchanged. All non-null stream handles, including legacy/per-thread sentinels, return801 before any loader/init/context/drain call. This is a bounded default-stream contract; no created stream, PTDS, event, async copy or overlap claim.

Null stream shares the existing cudaDeviceSynchronize sequence: ensure current context, drain only matching-context retired modules, then call Driver synchronization. Map raw initialization/context/sync Driver errors once; preserve drain Runtime errors. Boundary catches panics and records TLS errors; success preserves earlier error. Actual backend operations currently complete synchronously, so this may wait more broadly than a future independent stream implementation; no other streams are supported today.

The user has delegated routine implementation choices. Initial consideration of a blocking cudaMemcpyAsync alias was deferred after consulting CUDA12 API synchronization rules: implementing real async semantics and host-memory lifetime requires a separate design.

1. Add failing Rust tests to state_tests.rs for invalid-stream GPU-free rejection, ordered context/drain/sync, short circuits, Runtime-vs-Driver error domains, current-context preservation and TLS. Add failing Runtime28 profile assertion.
2. Extract an injectable synchronization helper in device.rs; share it between cudaDeviceSynchronize and the new lib.rs export. No extra Driver symbol resolution.
3. Extend include/ct_cudart.h, tests/p09a_runtime.def and the current profile/checker to28. Preserve14/21/22 subsets and historical results. Migrate active native counts/stdout oracles.
4. Add official-header native ABI fixture/runner: actual device memory roundtrip and ordinary context preservation, invalid-handle no-loader, absentDriver35 and provider synchronize709 controls; exact28 exports. Use strict independent observation validation.
5. Freeze source, run Runtime/workspace/Python checks, existing CUDA vectorAdd replay and static matrixMul triage with fresh Runtime28 reference, independent subagent review and privacy/baseline checks. Record results with bounded claims.

Official semantics reviewed: https://docs.nvidia.com/cuda/archive/12.0.1/cuda-runtime-api/api-sync-behavior.html
