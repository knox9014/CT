# Relaxed u32/b32 global operands: development verification

2026-10-25. This is working-checkout verification on top of `219e6e5`, not
an immutable clean acceptance or release. Historical P04c results are unchanged.

## Change

`ld.global.u32/b32` may write a declared U64 bit-container register, zero-extending
the loaded bits. `st.global.u32/b32` may read such a register and store only its
low 32 bits. The memory type, access size and alignment remain U32/four bytes.
Named scalar u32 globals retain the existing `.u32` ordinary/volatile contract.
The emitter uses explicit OpUConvert between memory and register values.

This implements a bounded part of [PTX 12.0.1 section 9.4.1](https://docs.nvidia.com/cuda/archive/12.0.1/parallel-thread-execution/index.html).
Signed widened loads/stores, relaxed parameter/cvt operands, narrow types, floating
relaxation and pointer provenance/alignment changes are not part of this change.

## Actual checks

- Before implementation, positive parser and translation tests failed at the
  widened load with `invalid destination register/type`. An initial fixture
  declaration syntax error was corrected before recording this expected failure.
- Rust workspace: **141 passed, 0 failed, 3 ignored**. Ignored native tests were
  not enabled; their old accepted results are not reused as current execution.
- Standalone Runtime: **77 passed**. Python discovery: **152 passed**.
- Workspace fmt/clippy with warnings denied, Runtime fmt, compatibility and
  Runtime profile checks, and static coverage checks passed. Static checks are
  not execution evidence.
- Pinned spirv-val accepted the PTX8/sm52 fixture's emitted module under
  `opencl1.2`. Module SHA256:
  `7f0d3024639b4797bf1bd1ac73e318f0a499efc98ffc3072af9382a4d90be727`.
- Native Driver regression: **24 cases / 384 output words**, Intel(R) Arc(TM)
  B390 GPU. Both supported PTX header profiles executed. Inputs include zero,
  sign-bit-set and all-one values; destinations are poisoned before loads.
  Store high bits are discarded, output neighbors remain unchanged, input
  buffers remain byte-identical, and named globals use the same conversion path.
- Fixture SHA256:
  `1c4af347e2f4959da5a5c7afffa232b7400ec5fe3971a187619ac2d333280f9d`.
- Fresh-target Driver DLL SHA256:
  `e7c0403c208f206f2d2d932b754ebd4788d9c095be695899b993b85ddcc05952`.
- Independent source reviewer found no blocking correctness issue. The suggested
  dedicated too-narrow memory-operand negative test was added and passed.

The default build target initially encountered LNK1114/error5 while overwriting
an import library. A fresh local target with incremental compilation disabled
completed the workspace tests/build; no historical target was deleted or reset.
The numerical harness accepts `--driver` to bind the intended DLL explicitly.

## Reproduction

From the repository root, with the existing pinned validator prepared:

```powershell
$env:CARGO_INCREMENTAL='0'
cargo test --workspace --target-dir .cache/relaxed-memory-target
cargo build -p ct-cuda --target-dir .cache/relaxed-memory-target
cargo run -p ct-codegen-spirv --example translate -- tests/fixtures/relaxed_memory.ptx .cache/relaxed-memory.spv
python scripts/validate_spirv.py .cache/relaxed-memory.spv --tool .cache/universal-foundation/spirv-build/tools/Release/spirv-val.exe
python tests/relaxed_memory_check.py --driver .cache/relaxed-memory-target/debug/ct_cuda.dll
```

Logs and generated binaries stay ignored under `.cache`. The fixture is a
hand-written regression matching an nvcc-observed instruction shape; it is not
a newly compiled genuine nvcc consumer or unchanged upstream application.
The existing 52-case clean acceptance lane has not been extended or rerun for
this change. AMD, NVIDIA parity, supported-host compiler qualification and
performance measurements remain unverified.

Next: bind this behavior to a genuine producer/application case, then separately
address signed widening and access-specific pointer alignment before broadening
the profile. See [implementation plan](superpowers/plans/2026-10-25-relaxed-memory-width.md).
