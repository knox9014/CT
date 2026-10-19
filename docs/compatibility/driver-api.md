# Experimental M1/M2 Driver API subset

Windows x64, Arc B390 tested. Library: `ct_cuda.dll`, loaded by explicit absolute path in the independent C test. This is not nvcuda.dll replacement installation, complete CUDA ABI/version conformance or existing application compatibility. No other CUDA symbols are currently promised.

Export calling convention: Windows CUDA `__stdcall` / Rust `extern "system"` (unified x64 ABI). `CUdevice` and `CUresult` are 32-bit signed int; `CUdeviceptr` is 64-bit unsigned; context is an opaque pointer-sized token, never dereferenced. Legacy `_v2` context create has three arguments; newer context-create variants are not exported.

| Exports | Supported contract |
| --- | --- |
| cuInit | flags=0, idempotent initialization of the Intel backend |
| cuDeviceGetCount, cuDeviceGet | native Intel GPU list and ordinal validation |
| cuDeviceGetName | bounded NUL-terminated name; positive buffer size required |
| cuDeviceGetAttribute | attributes 1..4 (max threads/group and X/Y/Z dimensions); other values return NOT_SUPPORTED and output 0 |
| cuCtxCreate_v2, cuCtxDestroy_v2 | flags=0; monotonic non-dereferenced handles; destroy releases owned native allocations on normal path |
| cuCtxGetCurrent, cuCtxSetCurrent | per-thread current-context stack; null set detaches the top entry |
| cuCtxPushCurrent_v2, cuCtxPopCurrent_v2 | attach/detach an existing live context; foreign host threads start with no current context |
| cuCtxGetDevice, cuCtxSynchronize | current-context device and native completion |
| cuMemAlloc_v2, cuMemFree_v2 | positive size, device-native allocation, exact base for free |
| cuMemcpyHtoD_v2, cuMemcpyDtoH_v2 | synchronous transfers, interior device ranges allowed, crossing an allocation boundary rejected; zero bytes allowed only at a valid interior device address and performs no host access |
| cuGetErrorName, cuGetErrorString | static read-only strings for the explicitly implemented error subset |
| cuDriverGetVersion | explicitly returns NOT_SUPPORTED, output 0; no invented CUDA version |

Host pointers must refer to valid sufficiently sized memory for the operation. Null pointers are checked; arbitrary invalid non-null pointers cannot be safely validated by this C ABI. Device addresses are validated against current-context allocation ranges, with overflow checks. A freed numeric address may be reused by a later allocation as in ordinary pointer APIs; universal stale-pointer identity detection is not promised.

Error subset: SUCCESS=0, INVALID_VALUE=1, OUT_OF_MEMORY=2, NOT_INITIALIZED=3, NO_DEVICE=100, INVALID_DEVICE=101, INVALID_CONTEXT=201, NOT_SUPPORTED=801, UNKNOWN=999. Exact parity with every NVIDIA error-precedence edge case is not established.

Native transfers use pinned staging and a synchronous immediate list. Uncertain completion or staging cleanup failure poisons the context and retains potentially live resources until process exit. Subsequent operations fail rather than pretending recovery. Device-loss/timeouts and all allocation/cleanup failures have not been fault-injected. No production fault-recovery claim is made.

## M2 module and kernel extension

The M1 table above contains 20 exports. M2 adds four, bringing the experimental total to 24. Module, function and stream types are pointer-sized opaque handles. Module/function tokens are monotonic, owned by a context and never dereferenced as host pointers.

| Exports | Supported contract |
| --- | --- |
| cuModuleLoadData | bounded NUL-terminated text in the [M2 PTX profile](ptx-profile.md); current context required; malformed input returns INVALID_PTX=218, unsupported features return NOT_SUPPORTED=801 |
| cuModuleGetFunction | exact entry name in a current-context module; missing entry returns NOT_FOUND=500 |
| cuModuleUnload | synchronous destruction; invalidates the module's function handles |
| cuLaunchKernel | one-dimensional synchronous dispatch with kernelParams; checks device limits, pointer argument starts and context ownership; streams/shared memory/extra unsupported |

Stale or foreign module/function tokens return INVALID_HANDLE=400. Context destruction unloads owned modules before native context destruction. Uncertain native work or cleanup retains resources and poisons the context. Host pointer validity and dynamic kernel access bounds remain caller obligations.

Primary contexts, streams/events, cudart, cuBLAS and AMD remain unsupported. See [M2 results and limitations](../M2-RESULTS.md).

## M3b versioned entry-point extension

M3b adds `cuGetProcAddress` and `cuGetProcAddress_v2`, bringing the total to 26 exports. They select existing CT functions through explicitly supported version intervals, without implying broader support or advertising a CUDA driver version. See [lookup contracts and limits](driver-entrypoints.md) and [official-header consumer results](../M3b-RESULTS.md).
