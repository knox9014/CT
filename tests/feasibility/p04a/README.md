# Native global feasibility only

These CT-owned sources test a single initialized u32 SPIR-V global through the
original Level Zero API, not through CT's PTX compiler/Driver/Runtime. They are not
a required CUDA acceptance gate. They deliberately use one work-item and one4-byte
output. Full acceptance must add independent arrays/guards, lifecycle/failure tests
and unchanged genuine CUDA host programs.

Generate the SPIR-V with `python tests/feasibility/p04a/make_spirv.py .cache/p04a-probe/global.spv`.
Run the existing pinned spirv-val with `--target-env opencl1.2`. Compile native_globals.cpp
with installed x64 MSVC C++17 and the unmodified `.cache/reference/ze_api.h`, first
verifying header SHA2563e7967d37ce79a472205c9cc230da837173ba390686bc4017e980e1290e40feb
(the existing official oneapi-src/level-zero v1.27.0 header pin). Put the EXE beside
global.spv in the ignored probe directory and run there. Only the Windows System32
Level Zero loader is selected; no GPU driver installation or replacement occurs.

Expected JSON: reads[7,8,123], stored124, other_module7 and preserved_after_unload7.
This proves a bounded native mechanism on the tested Arc, not full P04, AMD/NVIDIA
behavior, arbitrary host pointers, device linking or CUDA translation support.
