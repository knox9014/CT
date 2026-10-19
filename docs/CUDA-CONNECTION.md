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
