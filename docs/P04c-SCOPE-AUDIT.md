# Next feature scope audit after P04b

2026-10-25. Preparatory source inspection only; no new feature implementation,
new native result or completion claim. Baseline: 7bffe16.

The proposed next slice is scalar u64 stored globals across the existing CUDA
Driver/Runtime path. The alternative is shared-memory/block-barrier support.
The latter unlocks block cooperation but requires a separate execution-semantics
design; the former extends the already verified global/symbol ownership path.
Subsequently the user selected scalar u64 globals on 2026-10-25. The concrete
design is proposed in `superpowers/specs/2026-10-25-u64-global-design.md`.

## Confirmed source dependencies

- `ct-ptx/src/lib.rs`: GlobalStorage currently owns only MutableU32 initializer
  bits; Ty/ParamKind already represent U64 for other operations.
- `ct-ptx/src/parser.rs`: aligned scalar .u64 declarations are currently retained
  as Unsupported; direct named-global addressing and load/store validation allow
  the bounded u32 storage profile only. Supporting a declaration alone will not
  enable valid typed accesses.
- `ct-codegen-spirv/src/emit.rs`: exported stored globals use a u32 pointer/type
  and initializer. HostAccessINTEL/linkage and cross-kernel storage ownership must
  be preserved for additional widths.
- `ct-cuda/src/modules.rs`: the Driver module path filters globals by the same
  MutableU32 storage profile.
- `ct-backend-intel/src/modules.rs`: expected exported-global registration and
  native global lookup currently validate four-byte sizes. Expected type width,
  returned size, alignment and nonoverflowing address extent must stay consistent.
- `ct-cudart/src/registration.rs`: eligibility currently accepts size4 metadata
  with version1 and zero flags. Additional accepted sizes must not silently admit
  arrays/constants/extern variables or unsupported PTX module contents.
- `ct-cudart/src/kernels.rs`: immutable binding publication checks must agree with
  each registered variable, including mixed-width modules and partial failures.
- `ct-cudart/src/symbols.rs`: transfer preflight is bounded by four bytes before
  symbol lookup. A width-dependent limit needs an explicit error-precedence design;
  simply replacing 4 with 8 would weaken existing four-byte range rejection.

## Existing negative controls must migrate deliberately

`tests/fixtures/p09a2/default_unsupported_global.cu` deliberately uses a volatile
u64 global and expects error801. P04a/default-runtime producers, independent
oracles and evidence validation retain this control. With u64 enabled, this input
becomes a positive workload and must not continue to be labeled unsupported.

The new design must identify a genuine still-unsupported replacement, verify its
generated PTX/registration metadata and define producer/pinned-input transitions.
Historical accepted manifests and clean50 reports must remain unchanged. Removing
the negative gate or accepting any failure is not a valid migration.

## Required evidence for the proposed slice

Parser/type/initializer checks, SPIR-V validation, strict native binding checks,
mixed u32/u64 modules, unchanged genuine nvcc hosts, host symbol address/size/copy
queries, partial byte transfers with guards, context separation, retirement and
fresh replay. Use values with nonzero upper32 bits and boundary arithmetic so
truncation cannot pass. Preserve the existing supported u32 behavior and ABI.

Scope selection and a reviewed concrete design precede product code changes.
The feature direction is selected; detailed design approval and implementation
remain separate from this source audit.
