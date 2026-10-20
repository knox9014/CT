# M3n / P03f: integer min/max and abs/neg

Validated 2026-10-20 on Windows x64 / Intel Arc B390. Generic PTX translation
now accepts min/max.s32/u32/s64/u64 and abs/neg.s32/s64 (12 spellings).
Min/max compare with the declared width/signedness and select original operand
bits. Neg uses unsigned zero-minus-input at the declared width; abs selects
negation only for negative signed input. No undefined signed-overflow operation
is emitted. At signed minimum, abs/neg retain the high-bit-only representation
under this bounded two's-complement profile, tested against a masked CPU oracle.
This is not NVIDIA parity evidence. Reference:
[PTX integer arithmetic](https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html).

No CUDA exports, argument ABI, memory alignment or trust boundaries changed.
Float/narrow/packed/relu/saturation variants and negative-token immediate syntax
remain outside this extension. No per-kernel replacement is used.

## Evidence

- Parser and codegen RED runs rejected the unsupported min source before
  implementation. Two parser tests and one codegen test then passed; negatives
  cover wrong types, widths, arity, modifiers and uninitialized inputs. Codegen
  checks signed64 comparisons/selects and unsigned-width subtraction.
- Rust82 including prepared ignored native/producer/failure checks, Python21,
  rustfmt and warnings-denied all-target Clippy passed.
- [Native harness](../tests/m3n_minmax_check.py) executes12 entries at sizes
  1/63/64/65/257/50000 using raw PTX, genuine plain/compressed nvFatbin and
  compressed alternative profiles. 288 cases passed2,421,600 exact integer
  outputs and36,864 output guards. Three input allocations are byte-checked.
- The shared arithmetic harness now accepts optional supplied input/oracle
  arrays; legacy defaults remain. Output payloads start as complements of
  expected values, with64 prefix/suffix guards and aligned interior pointers.
- Inputs include zero, one, all-one, signed minima/maxima, full-width patterns,
  ties and unequal64-bit pairs with equal low32 bits. Python uses unbounded
  signed arithmetic followed by a width mask. The upper alternative inverts
  every output bit, making its actual selection observable for every element.
  An input audit found the inherited64-bit generator had lost unary -1 when
  adding high-only pairs. A boundary test failed first, then explicit -1/+1
  inputs were added at indices8/9. Python21 and the full native matrix passed
  after the change; both signed extrema and zero/unit inputs are pinned.
- A hash-preserved M3m baseline rejects the new source with218/801 and a null
  module handle. Existing CUDA failure containment and memory checks remain.

M3m regression passed576 cases/4,843,200 results/73,728 guards. M3l passed384
cases/3,228,800 results/49,152 guards, including the shared helper's legacy
defaults. M3k passed288 cases/2,421,600 results/37,152 guards and its
official-header C/CLI consumer passed771 results/387 guards with executable
and input bytes preserved. This new consumer is Python,
not a new C consumer or unchanged upstream application.

## Reproduce and scope

Before rebuilding, preserve a built M3m DLL and SHA-256 in ignored
.cache/m3n-baseline. A new checkout can build c3e57b5 separately without
resetting another checkout. Producer prerequisites follow [M3d](M3d-RESULTS.md).

```powershell
$env:CARGO_INCREMENTAL = '0'
./scripts/run_m3n_smoke.ps1
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py'
python scripts/check_compatibility_profile.py
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
```

[M3k ABI/memory limits](M3k-RESULTS.md) remain. AMD/NVIDIA execution and
official spirv-val are unverified; development continues on Arc. Full P03 and
general CUDA compatibility are not complete. Local logs and generated/vendor
binaries remain ignored. Preexisting license/Cargo/README changes are preserved
and excluded; local tests include their metadata-only edits.

## Independent review

A separate subagent reviewed c3e57b5..2d029df and the subsequent boundary-test
and documentation changes. No Critical, Important or Minor findings. It
independently ran the two parser tests, one focused translation test and the
new boundary unittest, and validated the manifest. CPU mutation checks confirmed
the inputs detect wrong signedness, reversed min/max, missing unary work,
minimum-to-zero behavior and64-to32 truncation. It did not independently
execute GPU/regression runs or establish NVIDIA/AMD/spirv-val/upstream parity.
GPU evidence above comes from the implementer. Keep as a stacked draft on M3m;
no merge.
