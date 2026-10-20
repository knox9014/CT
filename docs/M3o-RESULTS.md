# M3o / P03g: signed integer literals and mov aliases

Validated 2026-10-20 on Windows x64 / Intel Arc B390. Integer instruction
operands accept one optional unary + or - before a decimal, lowercase0x hex
or leading-zero octal literal. Positive magnitudes fit the U32/U64 operand
container; negative magnitudes are at most2^(width-1), including signed minimum
and negative zero. Negative values become width-matched two's-complement bits,
including for unsigned/bit instructions. Instruction signedness is unchanged.
mov.s32/s64 now alias the existing integer move.

This is a deliberate subset of [PTX constant evaluation](https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html).
No U suffix, general expression/parentheses, float/predicate literal, signed
register/builtin operand, signed memory offset or signed initializer is added.
Existing positive literal range checks remain. No lexer sign changes,
codegen/IR operation, CUDA export, ABI or memory/trust contract changed.

## Evidence

- The new parser test failed on unsupported signed mov before implementation.
  Three parser tests passed: exact bits at both widths/radices/signed minima,
  zeros, positive full-width patterns, and use in add/cvt/shift/setp/selp/store.
  Rejection cases cover magnitude overflow, invalid octal, repeated signs,
  suffixes/expressions, register/builtin/float/predicate and address operands.
- Rust85 including prepared ignored native/producer/failure checks, Python21,
  rustfmt and warnings-denied all-target Clippy passed.
- [Native harness](../tests/m3o_immediates_check.py) contains32 entries:
  mov/add x two widths x eight literal forms. Sizes1/63/64/65/257/50000 and
  raw PTX, genuine plain/compressed nvFatbin, compressed alternative profiles
  produced768 cases,6,457,600 exact outputs and98,304 output guards.
- Each payload starts as the complement of its expected output, with64 prefix
  and suffix guards. Three input allocations are checked byte-for-byte and
  pointers reference aligned interior addresses. Python expected values are
  explicit bit values and modular addition, not PTX token parsing.
- Literals cover negative decimal one/minimum, negative hex, negative octal,
  positive all-one hex, both signs of zero and positive octal. Native octal
  values010 are deliberately different from decimal10. The higher alternative
  inverts every result, making selection observable for every element.
- A hash-preserved M3n baseline rejects the new source with218/801/null.
  Out-of-range negative literal loading is rejected with218/801/null; a valid
  65-output/128-guard kernel then recovers. Recovery is excluded from768 totals.

The final distinct-octal768-case rerun passed. M3n passed288 cases/2,421,600
results/36,864 guards and M3m passed576/4,843,200/73,728. M3k passed288 cases/
2,421,600 results/37,152 guards; its existing official-header C/CLI consumer
passed771 results/387 guards with executable/input bytes preserved.
This is a synthetic Python CUDA
consumer, not a new C or unchanged upstream application.

## Reproduce and limits

Preserve a built M3n DLL and SHA-256 in ignored .cache/m3o-baseline before
rebuilding. New checkouts can build bf88a51 separately without resetting
another checkout. Producer prerequisites follow [M3d](M3d-RESULTS.md).

```powershell
$env:CARGO_INCREMENTAL = '0'
./scripts/run_m3o_smoke.ps1
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py'
python scripts/check_compatibility_profile.py
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
```

Full P03/general CUDA, AMD/NVIDIA parity and official spirv-val remain
unverified. [M3k ABI/memory limits](M3k-RESULTS.md) and trusted caller boundary
remain. Local logs/generated/vendor assets stay ignored. Existing uncommitted
license/Cargo/README edits are preserved and excluded; local tests include
their metadata-only changes.

## Independent review

An independent subagent reviewed bf88a51..f0b72e0: no Critical or Important
findings. It independently passed the initial two parser tests, inspected the
native checks and recomputed case/output/guard totals. Its one Minor suggestion
was explicit conversion source-width AST/range coverage. The implementer added
conversion_literal_range_and_bits_follow_source_width, inspecting both widening
and narrowing source bits and rejecting an out-of-range32-bit source despite a
64-bit destination; full Rust85/Python21 checks passed. No findings deferred.

The reviewer did not independently judge actual GPU/regression execution,
NVIDIA/AMD/spirv-val, final results/manifest documentation, or the later
conversion test. These are distinct from implementer checks; hardware/tool
limits remain unverified. Keep as a stacked draft on M3n; no merge.
