# R2b bootstrap resolver correction

CT now resolves four audited bootstrap names for ABI requests through12090: `cuInit`, `cuDriverGetVersion`, `cuDeviceGetCount` and `cuGetProcAddress`. For these stream-independent APIs, flags2 selects the same real implementation as the legacy search. The self-lookup still selects four arguments at11030..11999 and five at12000..12090.

**This is function-address lookup compatibility, not CUDA12.9 Driver support.** `cuDriverGetVersion` still returns801/output0. Other names retain the12000 request ceiling and flags2 rejection. In particular, memcpy/memset/event-record/launch APIs do not gain PTDS/PTSZ semantics; the11040 `cuCtxCreate` ABI transition remains unavailable. No exported symbol or GPU arithmetic feature was added.

## Verified Runtime boundary

The unchanged CuPy14.2.0 Windows wheel's `runtimeGetVersion()` returns12090. Its source calls the statically linked Runtime; `_getLocalRuntimeVersion()` is a separate dynamic Runtime path. NVIDIA documents that [Runtime version queries have not initialized CUDA since12.0](https://docs.nvidia.com/cuda/archive/12.9.1/cuda-runtime-api/group__CUDART____VERSION.html). Both nominal and observed queries succeed, with no Driver requests in the observed path. This identifies12.9, not the exact CuPy static Runtime patch build.

An official CUDA12.9.79 dynamic Runtime, taken from the authenticated [12.9.1 redistribution manifest](https://developer.download.nvidia.com/compute/cuda/redist/redistrib_12.9.1.json), provides the generation-matched native comparator:

| Probe | Nominal/observed result |
|---|---|
| CuPy static Runtime version | Success,12090; observed trace empty |
| Official Runtime DLL version | Success,12090; observed trace empty |
| Official Runtime DLL version with null output | Invalid-value1; trace empty |
| Official Runtime DLL device count | Error35, output remains−1; observed sole actual call is Driver version801/output0 |
| Original CuPy64-value task | Error35 during input creation; zero CUDA output words |

The official DLL and CuPy task have identical448-row bootstrap traces: one native loader lookup,446 resolver requests and one actual Driver version call. Requests resolve41 pointers, return308 null successes,96 unsupported errors and one invalid initial probe. These are request outcomes, **not404 mandatory missing APIs**. No `cuInit` execution is observed. Null-success and optional-feature lookup absence must not be equated with application failure.

The exact stream fallback rule comes from [the12.9 resolver contract](https://docs.nvidia.com/cuda/archive/12.9.0/cuda-driver-api/group__CUDA__DRIVER__ENTRY__POINT.html). Compile-only C++ assertions against the pinned official headers verify the three primitive signatures and both resolver signatures. The actual Rust tests verify real returned addresses, recursive calls through both ABIs, boundaries, invalid inputs, concurrent lookups and unchanged version-query errors. The existing virtual target controls PTX selection; it does not authorize a Driver-version number, especially before its cuInit policy latch.

## Source and artifact identity

- Frozen source fingerprint: `3d424bdbae0c4905d8b34e7d05074c1757d14b8b6a1233930e1b37c9ae39d48e`.
- Private source checkpoint: `51abd81e1377be25a66f54b217724a2ca7e7dbba`; tree `fc2195bd538d76024f1772076924435990ced145`. Ordinary reporting edits followed; product fingerprint is unchanged.
- Native comparator capture: `e57bee99667c4f8f90bc0d6e0df8715c`, SHA256 `13858221d22bef3e36f7443026e1981d26e2bf435a537156cc5295d0a20dbceb`.
- Native local recheck SHA256: `fcf1b10f0f67c3163c16a9c31fcb874878e8f8e060df1ccfaebc2d0b9a656911`.
- Fresh unchanged-CuPy task capture: `bd6d5994086f48908c961318144e3dbc`, SHA256 `7485ffac3f985f8f835e31e9f0b522ef450bc7f3ab234f48715dbfdcd7c7aaef`.
- CuPy local recheck SHA256: `1790875b4dd75401dc616b8c4d0882de8b0e6d3812362b93d3870cc7f504abc6`.
- Runtime archive SHA256: `179e9c43b0735ffe67207b3da556eb5a0c50f3047961882b7657d3b822d34ef8`;106 extracted vendor files verified. Runtime DLL SHA256: `760c38928bbe5759f7b31ed6692599eb7ec83cedd5702e84c2b72028a89837e1`.
- Official typedef header SHA256: `de38095e7fd221660ff578456e6984880f368838391640a810984f7dd9fee412`.

Native and CuPy captures each build their own fresh Driver from the same source. Their binary hashes may differ because their private build paths differ; each capture binds its own exact provider and loaded module identity. Local recheck validates saved observations/current inputs, not a new execution or authenticated attestation.

## Reproduce the bounded native probe

Prerequisites: Windows x64, the private Python3.14 environment and wheels from [the CuPy recipe](CUPY-BOOTSTRAP-RECIPE.md), Rust, and the existing authenticated `.cache/p09a2-producer/manifest.json` host-tool evidence. The native header check currently reuses that producer's verified MSVC environment. This is not yet a standalone installer or second-PC reproduction result; it does not invoke nvcc or compile a GPU kernel.

```powershell
New-Item -ItemType Directory -Force .cache/r2b-runtime-12.9
Invoke-WebRequest 'https://developer.download.nvidia.com/compute/cuda/redist/cuda_cudart/windows-x86_64/cuda_cudart-windows-x86_64-12.9.79-archive.zip' -OutFile .cache/r2b-runtime-12.9/runtime.zip
python scripts/run_runtime_bootstrap.py --environment .cache/r2-apps/cupy-env --wheels .cache/r2-apps/cupy-packages --archive .cache/r2b-runtime-12.9/runtime.zip
python scripts/run_runtime_bootstrap.py --recheck .cache/runtime-bootstrap-runs/<run-id>
```

Seven isolated native/version children and the separate original five-child CuPy task diagnostic are captured. The probes call version/device-count functions only, never allocation or launch. Immediately before each child, the tool rechecks source, interpreter, SDK/provider/ABI artifacts and bundle copies; CuPy cases additionally recheck installed wheel payloads. DLL loading paths and hashes are verified in the child. Native DLL instrumentation is explicit opt-in; default observation still requires a CuPy `.pyd`. The exact Windows API-set loader import used by the official DLL is supported, with each hook forwarding its own original import-slot implementation and restoring it afterward. Observation is diagnostic; pointer identity/timing/last-error transparency is not a nominal compatibility guarantee.

## Review and remaining scope

Independent review rejected an unjustified numeric Driver version and confirmed the narrow resolver correction. Follow-up findings tightened signed/unsigned/status checks, rejected advanced prefixes, enforced nominal/observed separation and moved input identity checks ahead of execution. Regression tests first failed on those cases and passed after fixes. Final read-only review found no remaining material issue in this scope.

The clean private source checkpoint passed CPU11/11: formatting, Clippy, Python281, Rust209 with4 existing ignored tests, Runtime129 and both profile/registry checks. All five resolver tests passed. Publication scanning and diff checks passed; protected11 files and original root HEAD/index were preserved. These are bounded verification results, not a general security guarantee or release approval.

The first ordinary-target build encountered an existing Windows file-lock/ACL linker failure; isolated fresh targets recovered, and the intended flags2 test then failed against the old resolver before implementation. The official Runtime initially exposed a different Windows loader API-set import; the bounded parser/forwarder was extended and tested rather than bypassing validation.

CuPy remains blocked on the actual Driver-version query. R2's full common initialization bundle and R3 numeric-version policy are unfinished. Existing R1 GPU arithmetic/lifetime qualifications remain historical; this step does not relabel them as new CuPy or CUDA12.9 success. Whole-framework support, useful end-user workload acceptance, second Intel PC, performance, NVIDIA comparison and AMD remain unqualified. Vendor bytes, tool environments, captures and raw logs remain ignored; no upload or root staging/commit was performed.
