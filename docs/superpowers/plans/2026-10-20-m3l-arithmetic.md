# M3l / P03d modular integer arithmetic

Continue the authorized P03 sequence on Arc only. Bounded extension of the
existing parser/emitter; CUDA ABI and memory contracts stay unchanged.

## Contract

Accept add/sub/mul.lo/mad.lo for s32/u32/s64/u64. All operands and result
have the declared width; arithmetic preserves low32/64 bits modulo2^width.
No saturation, carry, high/wide multiply-add, division, signed immediate
syntax or narrow integers are added. Reuse unsigned bit-container IR.
Mad must use its actual width for both product and addition.
Reference: [PTX integer arithmetic](https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html).

## Steps

- [x] Parser tests cover16 spellings and reject wrong width/arity/modifiers;
  observe unsupported-source RED then reuse existing Op variants.
- [x] Codegen test verifies64-bit mad product and sum; observe RED then
  replace hardcoded U32 result IDs with the operation type. Run Rust/lint.
- [x] Native Driver API harness loads generated generic kernels with input
  arrays, exact Python modular oracle,32/64-bit high-bit/boundary values,
  sizes1/63/64/65/257/50000, guards and unchanged inputs. Test raw/plain/
  compressed/alternative PTX; preserve baseline rejection and hash.
- [x] Run existing M3j/M3k regressions including official-header C consumer;
  update profile/results, independent subagent review (no actionable findings).
- [x] Final publication privacy/identity scans passed; stacked
  [draft PR15](https://github.com/knox9014/CT/pull/15) on M3k created and attached.
  No merge.

## Review focus

Width propagation through both mad stages, signed and unsigned modular
equivalence, overflow and missing writes, read-only inputs and guard extents,
alternative selection and baseline rejection. AMD/NVIDIA hardware and official
spirv-val remain unverified, not prerequisites for Arc development. No new
independent C consumer is claimed; M3k's C application is regression coverage.
