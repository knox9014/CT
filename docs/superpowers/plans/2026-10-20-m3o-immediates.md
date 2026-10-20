# M3o / P03g signed integer immediates

Bounded parser extension: one optional unary + or - before a decimal/0x
hexadecimal/leading-zero octal integer instruction operand. Positive magnitude
must fit the operand's U32/U64 bit container; negative magnitude must be at most
2^(width-1), including signed minimum and negative zero. Convert negative values
to two's-complement operand bits. Applies also to unsigned/bit instruction
operands at that width; does not change operation signedness. Add mov.s32/s64
aliases to existing integer Mov. No new codegen/ABI or lexical sign changes.

Reject signed register/builtin operands, float/predicate constants, repeated
signs, out-of-range magnitudes, suffix U, binary expressions/parentheses, and
signed offsets/initializers. Existing positive literals stay width-checked.
These are deliberate subset limits, not full PTX constant-expression support.
Reference: [PTX constant evaluation](https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html).

- [x] Parser tests prove exact bits at both widths/radices/limits, instruction
  use and rejection; observe RED then implement strict operand-local parsing.
- [x] Native32-entry mov/add matrix (eight literals x two widths x two uses),
  six boundary sizes and raw/plain/compressed/alternative profiles. Exact
  outputs/guards, input preservation, baseline hash/rejection and profile choice.
- [x] Full Rust/Python/fmt/Clippy and M3n/M3m/M3k regressions including C/CLI;
  docs/manifest, independent subagent review. Conversion source-width coverage
  suggestion addressed; no deferred findings.
- [x] Final privacy/identity scans passed; stacked
  [draft PR18](https://github.com/knox9014/CT/pull/18) on M3n created and attached;
  no merge.
  Preserve/exclude preexisting license/Cargo/README changes.

Review focus: signed minimum without host overflow, no truncation/range bypass,
sign tokens cannot reach register/builtin/float/address parsing, bad octal,
operand width rather than result width (cvt/shift), existing pointer inference.
AMD/NVIDIA/official spirv-val remain unverified, not blockers for Arc work.
