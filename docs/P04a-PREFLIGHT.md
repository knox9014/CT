# P04a native global feasibility

Observed2026-10-24 on the available Windows x64 Intel Arc path. This is a CT-owned
Level Zero/SPIR-V experiment, not execution through CT's PTX compiler/Driver/Runtime.
The existing C acceptance remains candidate258bf92 with44 required passes.

The364-byte SPIR-V fixture declares one initialized CrossWorkgroup u32 global with
standard LinkageAttributes Export and one single-work-item kernel. It reads and
increments the global. Original pinned spirv-val accepted it under OpenCL1.2.
The unchanged existing official Level Zero header pin was verified before compilation:
3e7967d37ce79a472205c9cc230da837173ba390686bc4017e980e1290e40feb.

SPIR-V SHA256:300302d6e60b6b857666fb82e591376c1fa7e41f338a88c07126cc495c7be361.
The public generator emits byte-identical input to the native-tested fixture.

Actual Level Zero observations:

| Check | Observed |
| --- | --- |
| First kernel reads initializer |7|
| Second kernel reads retained increment |8|
| Host writes123, next kernel reads it |123|
| Global after third increment |124|
| Second separately loaded identical module |7, distinct pointer|
| Second module after first module unload |7|

Both modules and the kernel/output/list/context were explicitly released successfully.
No product implementation, CUDA symbol API, multi-context result, failure recovery,
AMD/NVIDIA parity, concurrency/atomic behavior or performance claim follows from this
experiment. Output was one4-byte word, so it is not the later guarded-array oracle.

CT-owned reproducible sources: [probe and recipe](../tests/feasibility/p04a/README.md).
Vendor headers, native binaries, raw logs and machine/tool paths remain ignored.

Normative references: the [Level Zero SPIR-V guide](https://oneapi-src.github.io/level-zero-spec/level-zero/latest/core/SPIRV.html)
defines CrossWorkgroup pointer arguments, standard Linkage support and global-name
lookup via HostAccessINTEL or LinkageAttributes. The [module API](https://oneapi-src.github.io/level-zero-spec/level-zero/latest/core/api/apis/module.html)
defines zeModuleGetGlobalPointer. The [CUDA module API](https://docs.nvidia.com/cuda/archive/12.1.1/cuda-driver-api/group__CUDA__MODULE.html)
defines CUDA global lookup including allowing one output to be null. These describe
contracts; only the bounded experiment above was run here.

## Implementation finding: preserve host-visible unused globals

The first product Driver test found that Linkage Export alone preserved a used
u32 but Intel's native compiler removed an unused u32. Native GetGlobal returned
0x78000003 for the unused name. Adding GlobalVariableHostAccessINTEL capability
6187, SPV_INTEL_global_variable_host_access, and HostAccessINTEL ReadWrite (6188,
qualifier3, exact exported name) preserved both names. The patched binary passed
pinned spirv-val under opencl1.2 and native typed lookup for both4-byte addresses.

This supersedes the earlier assumption that Linkage alone sufficed. CT emits the
host-access decoration for all stored globals, alongside Linkage Export, while
no-global modules retain their old output. The current SPIR-V backend targets
Intel Level Zero; a future AMD backend must choose its own compatible lowering.
No dummy volatile reads or hidden user parameters are introduced.

Primary reference: [Level Zero SPIR-V environment](https://oneapi-src.github.io/level-zero-spec/level-zero/latest/core/SPIRV.html)
and [Khronos host-access extension](https://github.com/KhronosGroup/SPIRV-Registry/blob/main/extensions/INTEL/SPV_INTEL_global_variable_host_access.asciidoc).
