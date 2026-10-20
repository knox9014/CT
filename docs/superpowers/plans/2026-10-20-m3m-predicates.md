# M3m / P03e integer comparisons and select

Bounded continuation of the existing P03 parser/emitter on Arc. Accept
setp.eq/ne/lt/le/gt/ge for s32/u32/s64/u64 (24 spellings), and selp for
b32/u32/s32/b64/u64/s64 (six spellings). Result predicates and selected
integer bits retain their width. Signed comparisons bitcast operands to the
matching signed width. No float comparison changes, paired predicates,
boolean combining, predicate negation operand, narrow types or modifier support.
CUDA ABI, alignment and trust boundaries stay unchanged.

Reference: [PTX setp/selp](https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html).

- [x] Add parser width/predicate/arity/modifier tests; observe RED, implement.
- [x] Add signed64 SPIR-V compare and select type test; observe RED, implement;
  run Rust, Python, format and Clippy checks.
- [x] Arc CUDA consumer compares every selected integer bit with a Python
  relational oracle: signed extrema, equal pairs, high-bit patterns, both truth
  outcomes, sizes1/63/64/65/257/50000; raw/plain/compressed/alternative inputs.
  Check baseline hash/rejection, guards/input preservation and selected profile.
- [x] Run M3l/M3k regressions and C/CLI consumer. Independent subagent review;
  fix equality-input coverage finding with RED/GREEN and native revalidation.
  Docs/manifest updated; existing user edits preserved.
- [x] Final privacy/identity scans passed; stacked
  [draft PR16](https://github.com/knox9014/CT/pull/16) on M3l created and attached;
  no merge.

Review focus: correct signed width, relation opcode direction, full64-bit
selected values, real equal/less/greater and both predicate outcomes,
missing writes, existing branch/float comparisons, alternative selection.
Existing uncommitted license/Cargo/README edits are not part of this change.
NVIDIA/AMD execution and official spirv-val remain unverified, not blockers.
