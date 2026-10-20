# CUDA application connection: fixed project direction

User confirmed on 2026-10-19: CT must connect CUDA applications to Intel/AMD GPU execution. Standalone GPU demonstrations and PTX translation are intermediate milestones. The product goal remains existing CUDA API/ABI callers running through CT without per-application kernel replacements.

M2 verified a restricted PTX path through an explicitly opened CT DLL. Next is M3: a process-local application loader. System NVIDIA DLLs and vendor drivers must not be replaced. Existing executable/PTX bytes must be preserved and hashed. Driver API connection is distinct from CUDA Runtime/cudart, libraries and general AI application support.

## First connection increment (M3a)

Windows x64 standalone applications using normal named `nvcuda.dll` imports or `LoadLibrary("nvcuda.dll")` / `GetProcAddress` are the first target. A local CLI inspects PE imports and creates a fresh ignored execution bundle containing byte-identical application/PTX copies and CT under the application-local name `nvcuda.dll`. It starts the child only after preparation. The original directory, environment search paths, registry and system drivers are unchanged.

This follows the standard Windows unpackaged application DLL search order. It does not intercept absolute System32 loads, custom search flags, package graphs, activation-context redirection, KnownDLL precedence or arbitrary dependencies. Static imports outside CT's supported CUDA symbols are rejected before launch. Dynamic symbol requirements cannot be proved from the import table. Delay imports, ordinal CUDA imports, cudart and versioned `cuGetProcAddress` dispatch are outside this increment.

The CLI must describe inspection as compatibility triage, not proof a program will run. It must validate PE structure/bounds, reject non-x64/DLL images, prevent asset filename collisions, retain the child exit code and avoid printing personal paths in its own errors. Only explicit trusted programs are executed. Bundles may retain user inputs locally and stay ignored; no recursive copy of personal directories.

Verification uses two synthetic independent C consumers, built once with ordinary CUDA ABI imports: one statically imports `nvcuda.dll`, the other dynamically resolves it. Neither accepts a CT DLL path or contains CT loading logic. Both perform real GPU computation with external PTX. Hashes before/after staging must match; unsupported imports, malformed PE, invalid launch inputs, process argument quoting and nonzero exits are also tested.

This is an initial loader connection result, not full M3/v0.1 clearance. NVIDIA original execution and coexistence require NVIDIA hardware/software and remain unverified here.

References: [Microsoft DLL search order](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order), [NVIDIA Driver entry-point access](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__DRIVER__ENTRY__POINT.html).

## Versioned Driver connection increment (M3b)

The four- and five-argument CUDA function resolvers now connect canonical base-name/version requests to implemented CT functions. A consumer compiled solely with official NVIDIA headers obtains its function pointers through both resolvers and executes restricted PTX on Arc B390. The lookup ceiling, unsupported newer signatures, flags and error rules are explicit in [Driver entry-point support](compatibility/driver-entrypoints.md); exact checks are in [M3b results](M3b-RESULTS.md).

This extends M3a's supported loading paths. It does not complete external-app, NVIDIA original/coexistence, Runtime API or AMD verification. Further work remains anchored to an unchanged external CUDA program's actual requirements.

## Official sample adjustment (M3c)

NVIDIA's pinned vectorAddDrv host and kernel sources now run through CT with an adjusted module packaging path: actual NVRTC-generated PTX under the host's expected fatbin filename. Host source remains unchanged and the same executable that initially failed now passes after CT-side changes. Signed operations, proven unannotated pointer parameters, unused global declarations and compute-mode lookup cover observed compiler/application needs. See [M3c evidence and exact adjustments](M3c-RESULTS.md). Original binary fatbins and NVIDIA execution comparison remain outstanding.

## Genuine fatbin connection (M3d)

The same official host now also runs with a real NVIDIA nvFatbin-created binary container holding one uncompressed PTX module. CT decodes the container itself and passes selected PTX through its existing translator; no vendor decoding library is used at runtime. Compressed/multiple PTX, nonempty JIT options and runtime wrappers are explicitly rejected. See [M3d evidence](M3d-RESULTS.md) and the [supported format](compatibility/fatbin-profile.md). Original nvcc build parity, broader application formats and NVIDIA comparison remain outstanding.

## Compressed fatbin connection (M3e)

CT now also decodes one LZ4-compressed PTX module, with exact size checks and a
pre-allocation output cap. The unchanged official host and CLI passed with real
nvFatbin compressed output on Arc B390. Renamed subtraction semantics and
malformed-input recovery were separately checked. See [M3e evidence](M3e-RESULTS.md).
Multiple PTX selection/linking remains the next container-level task; the goal
continues through general instruction semantics, Runtime/library coverage and
hardware-verified AMD execution. Kernel names/hashes never choose replacements.

## Bounded alternative selection (M3f)

CT now enumerates bounded known-profile alternatives, validates their entry/ABI
and metadata/body agreement, and chooses8.0/sm_52 over7.0/sm_50 independent of order.
Real nvFatbin inputs passed48 native combinations with changed arithmetic and
entry names, plus rejection/recovery and repeated resource-cycle checks.
This completes the first narrow selection policy, not general linking, multiple
entries, unknown-profile fallback or CUDA Runtime registration. See [M3f results](M3f-RESULTS.md).

## Multiple kernels in one module (M3g / P02)

The parser/code generator and Intel backend now preserve1..32 entries in one
native module. Function handles retain their module/entry ABI; unload and context
destruction invalidate all corresponding functions. Raw/plain/compressed and
alternative-profile checks passed144 GPU combinations. A separate ordinary CUDA
consumer built with NVIDIA headers also passed through app-local loading and the
public CLI. This consumer is synthetic; stored globals/device calls, Runtime and
AMD remain future work. See [M3g results](M3g-RESULTS.md).

## M3h / P03a update

Synchronous CUDA grid/block x/y/z now map directly to native three-axis launches,
with all12 coordinate registers and consistent device limit attributes. A
separate official-header synthetic C consumer and public CLI passed2D/3D matrix
checks with byte preservation. This remains a restricted Driver API path; P03
arithmetic/ABI expansion and Runtime/AMD support are later work.
See [measured M3h results](M3h-RESULTS.md).
