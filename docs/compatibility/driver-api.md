# Experimental M1/M2 Driver API subset

## P05a primary context extension

`cuDevicePrimaryCtxRetain`, `cuDevicePrimaryCtxGetState`, and
`cuDevicePrimaryCtxRelease_v2` share one default-flags primary context per device.
Retain does not select it; use set/push current explicitly. Nonfinal release
preserves resources, while final release removes them without popping TLS.
Inactive GetState is observational and returns flags=0/active=0. Over-release
returns201. Retain counts are checked and serialized with other runtime calls.

Released primary handles are tombstoned; stale current/explicit primary handles
return709 (`CUDA_ERROR_CONTEXT_IS_DESTROYED`). Explicit SetCurrent(NULL) can pop
the stale top. Re-retain obtains a fresh CT handle. Destroy(primary) returns201
without changing state. These deterministic CT guards and post-release handle
identity have not been compared to NVIDIA hardware. Cleanup errors preserve the
original error and quarantine uncertain native resources without retry.

Nondefault scheduling, pinned-memory APIs and legacy release/reset/set-flags
remain unavailable. This is not complete primary-context or Runtime support.
See the [design](../superpowers/specs/2026-10-21-primary-context-design.md).

### P05b reset extension

`cuDevicePrimaryCtxReset_v2` deactivates resources while preserving every retained
usage. GetState is inactive after reset; releases still consume outstanding usage.
Reset on an unused or inactive valid device is a nonallocating no-op. Retain can
explicitly create a fresh generation; only successful retain increments usage.
Remaining pre-reset references count toward the new generation's final release.
Reset never edits TLS. Failed cleanup quarantines resources without retry and
preserves usage. Existing allocations/modules/functions become invalid.

Old CT context handles remain stale709 even after fresh activation. Exact old
CUcontext reuse and GetCurrent parity after reset are NVIDIA-unverified; consumers
must explicitly reacquire/select after reset in this profile. Stale raw native
device pointer addresses may be reused after deallocation; generation safety for
them is not claimed. See the [reset design](../superpowers/specs/2026-10-21-primary-reset-design.md).

### P05c default flags and library consumers

`cuDevicePrimaryCtxSetFlags_v2` supports flags0 for an initialized valid device,
inactive or active, without activation or reference/resource/TLS changes.
Unknown bits outside0x1f or scheduling bits3/5/6/7 return1; recognized nonzero flags
return801 without effects. `cuCtxGetFlags` reports0 for supported current ordinary/
primary contexts; no current201, stale primary709, null output1. Valid output is
cleared after initialization before validating current state.

Flags0 selects CT's existing default policy; NVIDIA AUTO heuristic equivalence
and nondefault wait scheduling are unverified/unimplemented. Deprecated MAP_HOST
and LMEM bits are conservatively unsupported too. Independent official-header
producer/consumer DLLs test shared resources across explicit release and producer
unload. Test-only dependency copying is not automatic public-loader packaging.
See the [consumer design](../superpowers/specs/2026-10-21-primary-consumers-design.md).

## Ordinary context destruction correction

Destroy now pops exactly one caller stack entry only when the target is current.
Buried entries and other threads' stacks are unchanged. Destroyed ordinary IDs
are tombstoned before cleanup: later current-context operations report709, while
unknown IDs/no current remain201. GetCurrent clears output and reports709 for a
stale ordinary top under CT's deterministic query policy. SetCurrent(NULL) can
explicitly remove one stale top. Primary Destroy remains rejected without stack
edits. Cleanup failures retain the existing quarantine/no-retry behavior.

This matches the documented top-pop/cross-thread access rules; exact GetCurrent
and arbitrary post-destroy-handle error parity with NVIDIA is not established.
Tombstones consume process-lifetime metadata. No exports or ABI floors change.

## Original M1/M2 scope

Windows x64, Arc B390 tested. The original independent C test loads `ct_cuda.dll`
by explicit path. Later M3 consumers use process-local `nvcuda.dll` bundles;
the P05a extension above adds shared primary ownership. System driver replacement
and complete CUDA ABI/version conformance remain outside the tested scope.

Export calling convention: Windows CUDA `__stdcall` / Rust `extern "system"` (unified x64 ABI). `CUdevice` and `CUresult` are 32-bit signed int; `CUdeviceptr` is 64-bit unsigned; context is an opaque pointer-sized token, never dereferenced. Legacy `_v2` context create has three arguments; newer context-create variants are not exported.

| Exports | Supported contract |
| --- | --- |
| cuInit | flags=0, idempotent initialization of the Intel backend |
| cuDeviceGetCount, cuDeviceGet | native Intel GPU list and ordinal validation |
| cuDeviceGetName | bounded NUL-terminated name; positive buffer size required |
| cuDeviceGetAttribute | attributes1..4 (max threads/group and X/Y/Z dimensions), M3h5..7 (grid X/Y/Z limits, capped to I32_MAX), and20/compute mode as DEFAULT=0; others return NOT_SUPPORTED and output0 |
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

Native transfers use pinned staging and a synchronous immediate list. Uncertain completion or cleanup failure poisons the context and retains possibly live resources until process exit. M3i adds deterministic foreign-call failure probes and fatal LOST/RESET handling before submission. Real device loss/timeouts, actual loader unload and automatic recovery remain unverified. No production fault-recovery claim is made. See [M3i evidence](../M3i-RESULTS.md).

## M2 module and kernel extension

The M1 table above contains 20 exports. M2 adds four, bringing the experimental total to 24. Module, function and stream types are pointer-sized opaque handles. Module/function tokens are monotonic, owned by a context and never dereferenced as host pointers.

| Exports | Supported contract |
| --- | --- |
| cuModuleLoadData | bounded NUL-terminated text in the [PTX profile](ptx-profile.md), or M3d's [raw fatbin profile](fatbin-profile.md); current context required; malformed input returns INVALID_PTX=218, unsupported features return NOT_SUPPORTED=801 |
| cuModuleGetFunction | exact entry name in a current-context module; missing entry returns NOT_FOUND=500 |
| cuModuleUnload | synchronous destruction; invalidates the module's function handles |
| cuLaunchKernel | synchronous1D/2D/3D dispatch with kernelParams; checks per-axis limits, checked block volume, U32 global axis sizes, pointer argument starts and context ownership; streams/shared memory/extra unsupported |

Stale or foreign module/function tokens return INVALID_HANDLE=400. Context destruction unloads owned modules before native context destruction. Uncertain native work or cleanup retains resources and poisons the context. Host pointer validity and dynamic kernel access bounds remain caller obligations.

Primary contexts, streams/events, cudart, cuBLAS and AMD remain unsupported. See [M2 results and limitations](../M2-RESULTS.md).

## M3b versioned entry-point extension

M3b adds `cuGetProcAddress` and `cuGetProcAddress_v2`, bringing the total to 26 exports. They select existing CT functions through explicitly supported version intervals, without implying broader support or advertising a CUDA driver version. See [lookup contracts and limits](driver-entrypoints.md) and [official-header consumer results](../M3b-RESULTS.md).

## M3g multiple-entry module extension

Within the restricted [PTX profile](ptx-profile.md), a CUDA module owns one native
module with1..32 distinct entries. cuModuleGetFunction selects any such entry and
its argument ABI; multiple lookup tokens may refer to the same entry. Handles
retain module/context ownership. Module unload or context destruction invalidates
all its functions. Missing names return500/null, stale or foreign handles400.
Synchronous1D launch,26 exports and all existing trust/unsupported contracts remain.
See [M3g evidence](../M3g-RESULTS.md).

## M3h dimension extension

M3h extends the earlier1D restriction to all three grid/block axes and all12
PTX coordinate components. Validation is shared by CUDA and native entry paths,
before argument mutation or launch submission. Zero/over-limit dimensions and
oversized or overflowing block volume return INVALID_VALUE. The26 exported
signatures, synchronous semantics and module ownership rules remain unchanged.
See [M3h evidence](../M3h-RESULTS.md).

## M3i failure containment

Fatal native LOST/RESET errors poison the affected context even during allocation,
module creation and kernel setup. All device-free failures and uncertain
submission/completion/cleanup failures stop subsequent native work. Build-log
cleanup preserves the first error and retains an uncertain log handle. Ordinary
allocation OOM and nonfatal setup argument errors remain recoverable. Native
OOM maps to CUDA2; fatal/unknown errors map to999, without full NVIDIA parity.
The private test-only injection provider is absent from normal builds.

## M3k typed integer memory/argument extension

Explicit b64/s64 scalar parameters consume8 bytes in kernelParams and are not
classified as device pointers. Pointer parameters carry4/8-byte alignment and
require that minimum current-context allocation span. Alternative images must
match both argument kind and alignment. Unannotated u64 scalar inference and
packed/vector/structure arguments remain unsupported. See the restricted
[PTX contract](ptx-profile.md) and [M3k native evidence](../M3k-RESULTS.md).
