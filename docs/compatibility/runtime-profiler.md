# Runtime profiler control: no-collector mode

`cudaProfilerStart` and `cudaProfilerStop` are present in Runtime40. CT currently
has no active profiling collector. These APIs perform successful no-effect
control in that explicit mode, after establishing a valid Runtime/current
context and sampling any already-published asynchronous queue error.

They are idempotent, do not clear last error on success, do not start the worker,
reserve a queue node, drain pending work or call native synchronize. Runtime
initialization/current-context failures are mapped once and returned. Already
observed queue errors are in the Runtime domain and remain unchanged. Pending
work may complete or fail after the observation; these calls are not fences.

No fake enabled state, profiler Driver extension, collector callbacks, trace
files or environment-controlled capture option are implemented. Successful
control does not mean any profiling data was collected. Nsight/CUPTI or Intel
profiler integration and NVIDIA-reference behavior parity are not claimed.

The [pinned CUDA12 Runtime specification](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-runtime-api/group__CUDART__PROFILER.html)
describes active-tool context control, idempotence and possible prior async
errors. The no-collector behavior above is the explicit CT compatibility policy;
it is not a claim of complete profiling implementation. A future collector
integration requires a separate contract and actual trace validation.

MatrixMul diagnostics now use strict PE inspection and offline PTX translation
only (triage schema2). Removing its last import names does not execute the app
or qualify unsupported shared memory/barriers/FMA/device-selection behavior.
