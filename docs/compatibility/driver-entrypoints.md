# Experimental M3b Driver entry-point lookup

CT supports `cuGetProcAddress(const char*, void**, int, uint64_t)` and `cuGetProcAddress_v2(const char*, void**, int, uint64_t, int*)` as distinct Windows x64 exports. Addresses are available before `cuInit`; each returned function retains its own context, pointer and feature preconditions.

The legacy resolver uses the [CUDA 11.8 documented missing-symbol error](https://docs.nvidia.com/cuda/archive/11.8.0/cuda-driver-api/group__CUDA__DRIVER__ENTRY__POINT.html): NOT_FOUND=500 and null output. The newer resolver follows the [CUDA 12.0 lookup-status contract](https://docs.nvidia.com/cuda/archive/12.0.0/cuda-driver-api/group__CUDA__DRIVER__ENTRY__POINT.html): an unavailable entry returns SUCCESS with null pointer, and optional status 1 for missing names or 2 for an unavailable ABI version. A valid lookup reports status 0.

## Canonical name and version selection

Use CUDA base names, such as `cuMemAlloc`, not exported suffix spellings like `cuMemAlloc_v2`. Explicit suffix names are not lookup aliases. The following verified ABI floors select existing CT implementations; the default upper bound is 12000 inclusive.

| Canonical names | Minimum requested version | CT implementation |
| --- | --- | --- |
| cuInit, cuDeviceGetCount, cuDeviceGet, cuDeviceGetName, cuDeviceGetAttribute | 2000 | same-name export |
| cuCtxGetDevice, cuCtxSynchronize | 2000 | same-name export |
| cuModuleLoadData, cuModuleGetFunction, cuModuleUnload | 2000 | same-name export |
| cuFuncGetParamInfo | 12040 | same-name export through ABI request 12090; verified against the CUDA 12.9.79 typedef |
| cuDriverGetVersion | 2020 | same-name export; still returns NOT_SUPPORTED and zero |
| cuCtxCreate | 3020 | cuCtxCreate_v2, only through requested version 11039 |
| cuMemAlloc, cuMemFree, cuMemcpyHtoD, cuMemcpyDtoH, cuMemcpyDtoD, cuMemsetD8, cuMemsetD16, cuMemsetD32 | 3020 | corresponding `_v2` export |
| cuCtxDestroy, cuCtxPushCurrent, cuCtxPopCurrent | 4000 | corresponding `_v2` export |
| cuMemGetAddressRange | 3020 | cuMemGetAddressRange_v2; current-context live allocations |
| cuPointerGetAttribute | 4000 | same-name export; attributes8/9/11/12 only |
| cuCtxGetCurrent, cuCtxSetCurrent, cuLaunchKernel | 4000 | same-name export |
| cuGetErrorName, cuGetErrorString | 6000 | same-name export |
| cuDevicePrimaryCtxRetain, cuDevicePrimaryCtxGetState | 7000 | same-name export; default-flags P05a subset |
| cuDevicePrimaryCtxRelease | 11000 | cuDevicePrimaryCtxRelease_v2; legacy ABI unavailable |
| cuDevicePrimaryCtxReset | 11000 | cuDevicePrimaryCtxReset_v2; legacy ABI unavailable |
| cuDevicePrimaryCtxSetFlags | 11000 | cuDevicePrimaryCtxSetFlags_v2; only flags0 |
| cuCtxGetFlags | 7000 | current context default flags query |
| cuGetProcAddress | 11030..11999 | four-argument cuGetProcAddress |
| cuGetProcAddress | 12000..12090 | five-argument cuGetProcAddress_v2 |

The `cuCtxCreate` signature changes at 11040 in pinned NVIDIA typedefs. CT does not implement that newer signature and will not substitute a three-argument pointer for it. Older ABI versions below the listed floor are likewise unavailable, even when their signatures appear similar.

## CT policy limits

- `cuInit`, `cuDriverGetVersion`, `cuDeviceGetCount` and the five-argument `cuGetProcAddress` self-lookup accept audited ABI requests through12090. The parameter query also accepts requests through12090 for flags0/1. Other names retain the12000 ceiling; requests outside each audited ceiling return NOT_SUPPORTED=801. These are lookup ceilings, not an advertised CUDA driver version or completeness claim. The older resolver self-lookup still ends at11999.
- Flags0/default and1/legacy are supported. Flag2 selects the same real pointer only for those four audited canonical names, which have no per-thread-stream variants in the pinned12.0/12.9 typedefs. For other names flag2 remains NOT_SUPPORTED; other flag combinations return INVALID_VALUE=1. In particular, memcpy/memset/event-record/launch APIs with PTDS/PTSZ variants do not gain per-thread semantics from this fallback.
- Null required arguments and nonpositive versions return INVALID_VALUE. Valid output storage is reset to null and optional status to1 before rejecting inputs. Status on non-success is only this deterministic CT default, not a full NVIDIA error-precedence guarantee.
- Status may be null. All supplied non-null caller pointers must be valid and sufficiently sized, with output/status storage nonoverlapping. Arbitrary invalid pointers cannot be validated by the C ABI.
- Unknown names and explicit version-suffix spellings are unavailable. Source symbol text is not logged or retained.

Except for the parameter query noted above, version floors and signatures were verified against ignored NVIDIA 12.0.107 `cudaTypedefs.h`; acquisition hashes and real GPU evidence are in [M3b results](../M3b-RESULTS.md). No NVIDIA implementation code is used in the resolver. Existing [Driver API](driver-api.md) and [PTX](ptx-profile.md) restrictions remain in force.

The four bootstrap names were additionally audited against the official CUDA12.9.79 Runtime archive's `cudaTypedefs.h` and `cuda.h`. `cuGetProcAddress` still selects different four/five-argument signatures at12000; `cuCtxCreate` still rejects the unimplemented11040 transition. Lookup does not initialize the GPU or select virtual-target policy. Calling the returned `cuDriverGetVersion` still returns801/output0; request support alone cannot establish a successful Driver-version report. See the [bounded R2b plan](../superpowers/plans/2026-10-29-r2b-bootstrap-resolvers.md).


Event lookup floors: `cuEventCreate`, `cuEventRecord`, `cuEventSynchronize`,
`cuEventElapsedTime` use2000; `cuEventDestroy` resolves to `cuEventDestroy_v2`
from4000. These select the legacy/default-stream record signature, not PTDS.

# Device total memory lookup

Canonical `cuDeviceTotalMem` resolves to `cuDeviceTotalMem_v2` for the audited v3020 size_t-pointer ABI through the existing12000 ceiling. Legacy v2000/versions below3020 are rejected to avoid writing8 bytes into4-byte output storage. The suffixed spelling is a DLL export, not a canonical resolver alias. This does not grant a CUDA driver version/conformance claim.
