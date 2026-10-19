# ADR 0001: M0 native Intel execution path

Date: 2026-10-19. Status: accepted for the M0 experiment only.

## Decision

Use the installed Windows System32 Level Zero loader and a standalone Rust/MSVC executable to prove native SPIR-V kernel execution on Arc B390. No Rust package dependencies, CUDA shim, external compatibility engine or driver installer is involved.

Load ze_loader.dll with LOAD_LIBRARY_SEARCH_SYSTEM32. Represent only the needed Level Zero C ABI structures and function signatures; compare their full layouts with the official v1.27.0 header using MSVC. Select an Intel GPU by explicit nonempty name filter and fail on ambiguity.

Use a readable, synthetic vector-add SPIR-V fixture with Physical64/OpenCL Kernel addressing. The small Python encoder supports only this fixture's instruction subset; it is not CT's compiler or a general assembler. Its opcodes/enumerants were checked against the pinned Khronos grammar. The actual Intel driver compiled and executed the module. Official spirv-val was not available and was not run.

Use host allocations and distinct device allocations, explicit copy/barrier/kernel/barrier/copy, then queue synchronization with a 30-second timeout. Initialize host storage through raw pointer writes; create Rust slices only after successful GPU completion. Check results and output guards; release all successfully initialized resources on the normal path and check API return codes.

If submission/completion fails without confirming GPU completion, retain GPU-referenced allocations and the loader until process exit instead of freeing memory still in use. This is a standalone experiment, not a long-running production backend. Timeout/device-loss cleanup has not been fault-injected.

## Evidence

- Driver initialization and enumeration: success.
- 12 FFI structures: all sizes, alignments and field offsets match C/MSVC against the pinned header.
- 16 GPU cases: 201,928 logical results and 1,536 guard values checked, max absolute error 0.
- Kernel output-store removed as a controlled negative test: rejected at the first NaN output, exit code 1.
- Full workspace tests and explicitly enabled hardware test passed; clippy with warnings denied passed.
- Independent source review identified host-buffer initialization/aliasing risk; corrected to raw initialization and post-completion immutable borrowing. Targeted follow-up review marked the issue resolved.

## Consequences

The B390 native execution route is viable in this exact environment. That supports designing a CUDA-facing layer next. It does not establish a PTX translator, CUDA ABI, cudart, fatbin, AI-library, AMD or other Intel-device compatibility. Future backends need their own error handling, versioning, ownership and conformance design.
