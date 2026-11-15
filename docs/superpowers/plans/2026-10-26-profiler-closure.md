# Profiler import closure and safe offline matrix diagnosis

Implement Runtime cudaProfilerStart/Stop only in an explicit no-collector mode.
NVIDIA CUDA12.0.1 Runtime documentation describes active-tool control, idempotence
and possible earlier asynchronous errors; it lists cudaSuccess. CT has no
collector integration. Do not create traces, advertise native profiler control,
or claim NVIDIA-reference parity. Require normal Runtime/current-context
initialization, propagate already observed queue errors without waiting, otherwise
return successful no-effect control. No worker startup, queue node allocation,
implicit synchronization or mutable fake capture state.

Use TDD for generic no-collector behavior: init failure, known async error,
pending job does not block, repeated start/stop and no native sync/capture.
Add typed export/official-header ABI tests and real nvcc event+copy+kernel scope.
Add Driver-absent and benign queued-error controls; existing tests still pass.
Runtime exports38->40; Driver46 unchanged. Final counts apply only after native
validation, independent review and privacy scans.

Ruling: matrixMul diagnostics must never invoke the application as imports close.
Replace the old strict-run observation with strict-inspect, bind exact command and
outputs, bump triage schema2 and reject old-schema relabels. Handle either
unsupported named imports (blocked,strict inspect2) or no missing names
(unproven,strict inspect0). Offline PTX rejection remains a separate nonexecution
barrier. Test a closed-import synthetic image and forbid application/run commands.
The generic loader strict rejection remains unchanged for unknown symbols.

Finish docs/compatibility before freezing source. Native profiler capture chains
Runtime event regressions; fresh original vectorAdd capture/replay and matrixMul
inspection follow. All binaries/vendor files/raw logs stay ignored in .cache;
existing user-owned11 files remain unchanged. No staging/upload.

Sources: pinned .cache/upstream-profiler-12.0.76/include/cuda_profiler_api.h;
https://docs.nvidia.com/cuda/archive/12.0.1/cuda-runtime-api/group__CUDART__PROFILER.html


Execution: Runtime129/Python195 and source-bound native controls passed. Original
vectorAdd capture/replay passed. Matrix schema2 strict inspection has no missing
imports and returns0; PTX .shared line32 still blocks execution. No collector
capture is claimed. Independent review found no blockers. Detailed evidence:
[Profiler import closure results](../../PROFILER-IMPORT-CLOSURE-RESULTS.md).
