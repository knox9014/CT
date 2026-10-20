# M3m / P03e: integer predicates and full-width select

Validated 2026-10-20 on Windows x64 / Intel Arc B390. Generic PTX translation
now accepts setp.eq/ne/lt/le/gt/ge for s32/u32/s64/u64 (24 spellings) and selp
for b32/u32/s32/b64/u64/s64 (six spellings). Predicates retain their boolean
type; selected values preserve all32/64 bits. Signed comparison operands are
bitcast to the matching signed width before the relational operation.

No kernel-specific substitution, CUDA export, argument ABI, memory alignment
or source-trust boundary changed. Float comparisons/select are unchanged.
Paired predicates, predicate combining/negated predicate operands, extra
modifiers, narrow types and general CUDA support are not added. Reference:
[PTX setp/selp](https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html).

## Evidence

- RED: parser rejected integer selp; signed64 codegen source was unsupported.
  Two new parser tests and one codegen test then passed. Parser negatives
  cover width/arity/predicate-type/uninitialized/modifier violations; codegen
  checks signed64 bitcast operands for all four ordered relations and U64 select.
- Rust79 including prepared ignored native/producer/failure tests, Python20,
  rustfmt and warnings-denied all-target Clippy passed.
- [Native harness](../tests/m3m_predicates_check.py) executes24 entries over
  sizes1/63/64/65/257/50000 and four input forms: raw PTX, genuine plain and
  compressed nvFatbin, and compressed alternative profiles. All six select
  spellings occur across these entries.
- 576 cases passed4,843,200 exact integer outputs and73,728 output guards.
  Three input allocations are checked byte-for-byte. Each payload is initialized
  to the complement of the expected output and has64 prefix/suffix guards;
  pointers refer to aligned interior allocation addresses.
- Inputs include equal pairs, signed extrema, high-bit and deterministic
  full-width values. Equality is forced every fifth element. Relational truth
  selects the third input value, otherwise its bitwise complement. The Python
  oracle converts signed input bit patterns before host relational comparison.
  Explicit unequal64-bit pairs with identical low32 bits survive the equality
  override and detect eq/ne truncation; a dedicated input-coverage test pins them.
- The higher alternative swaps select arms; its expected result changes for
  every element, proving profile selection. Hash-preserved M3l rejects the new
  source with218/801 and a null module handle.

M3l native regression passed384 cases/3,228,800 results/49,152 guards. M3k
passed288 cases/2,421,600 results/37,152 guards; its official-header C/CLI
consumer passed771 results/387 guards with executable/input bytes preserved.
This new consumer is Python,
not a new independently compiled C consumer or unchanged upstream application.

## Reproduce and limits

Preserve the built M3l DLL and SHA-256 in ignored .cache/m3m-baseline before
changing the DLL. A new checkout can build cc9549f separately without resetting
another checkout. Producer prerequisites follow [M3d](M3d-RESULTS.md).

```powershell
$env:CARGO_INCREMENTAL = '0'
./scripts/run_m3m_smoke.ps1
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py'
python scripts/check_compatibility_profile.py
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
```

[M3k ABI/memory limits](M3k-RESULTS.md) remain. NVIDIA/AMD hardware comparison
and official spirv-val remain unverified; development/testing continues on Arc.
Full P03 is not complete. Local logs and generated/vendor binaries stay ignored.
Preexisting uncommitted license/Cargo/README edits are preserved and excluded
from this branch's commits; local tests include their metadata-only changes.

## Independent review

A separate subagent reviewed cc9549f..1eed6d0: no Critical or Important
implementation findings, one Minor input-coverage gap. It independently passed
34 focused Rust tests and checked opcodes against the cached Khronos grammar.
It found no unequal64-bit native inputs sharing the same low32 bits, allowing
a hypothetical eq/ne truncation to escape detection. The implementer treated
this as a material verification gap, added a regression that failed with zero
witnesses, then added explicit high-only pairs. Python20 and the complete
576-case native matrix passed after this fix. No product code changed in the
fix pass; no findings are deferred.

The reviewer did not independently judge GPU execution, NVIDIA/AMD parity,
official spirv-val or final manifest/results documentation. Those hardware/tool
limits stay unverified; GPU evidence comes from the implementer. Keep as a
stacked draft on M3l; no merge.
