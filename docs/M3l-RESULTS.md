# M3l / P03d: modular32/64-bit integer arithmetic

Validated 2026-10-20 on Windows x64 / Intel Arc B390. CT now accepts
add/sub/mul.lo/mad.lo for s32/u32/s64/u64:16 total spellings, nine newly
accepted. Signed and unsigned forms preserve the same low-width result bits
modulo2^32/2^64. Integer mad uses the declared type in both product and sum;
the previous U32-only emitter is no longer reused incorrectly for U64.

This extends the generic parser and SPIR-V emitter. No kernel-specific
replacement, CUDA export, IR operation or argument ABI was added.
Saturation, carry, high/wide mad, signed division, narrow integers and signed
negative-token immediates are outside this extension. See
[PTX integer arithmetic](https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html).

## Test evidence

- Parser RED rejected the newly requested spelling; two parser tests then
  passed for16 accepted spellings plus width/arity/modifier rejection.
- Codegen RED exposed U32 product type in64-bit mad after parser support;
  both product and sum now use the operation type, and the regression passes.
- Rust76 including prepared ignored native/producer/failure probes, Python19,
  rustfmt and warnings-denied all-target Clippy passed.
- [Native harness](../tests/m3l_arithmetic_check.py) executes16 entries at
  sizes1/63/64/65/257/50000 through CUDA Driver API, using raw PTX, genuine
  plain/compressed nvFatbin and compressed alternative profiles.
- The384 cases passed3,228,800 exact integer output comparisons and49,152
  output guards. Three read-only input allocations are checked byte-for-byte.
  Output payloads start as bitwise complements of expected values;64 guards
  before and after each payload catch stray writes. Interior pointer arguments
  exercise the existing ownership/ABI path.
- Input triples include zero, one, all-one, signed extrema and deterministic
  full-width patterns. Tests exercise overflow of multiplication/addition,
  underflow, both signedness spellings and high64 result bits. The Python oracle
  computes unbounded integer expressions then masks the final width.
- The higher alternative swaps add/sub behavior, so its actual selection is
  checked against a different CPU expectation. A hash-preserved M3k baseline
  rejects the new module with218/801 and a null module handle.

Existing M3j native regression passed504 oracle cases/4,032 result comparisons/
10,752 guards and its official-header C/CLI consumer. M3k passed288 cases/
2,421,600 exact outputs/37,152 guards and its C/CLI consumer's771 outputs/
387 guards, with executable/input bytes preserved. The new arithmetic harness
is a Python CUDA consumer; it is not a new independently compiled C application
or an unchanged upstream application.

## Reproduce and scope

Before changing the DLL, preserve a built M3k DLL and SHA-256 in ignored
.cache/m3l-baseline. A new checkout can build bfb12bb separately without
resetting another checkout. Producer prerequisites follow [M3d](M3d-RESULTS.md).

```powershell
$env:CARGO_INCREMENTAL = '0'
./scripts/run_m3l_smoke.ps1
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py'
python scripts/check_compatibility_profile.py
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
```

The [M3k memory/ABI restrictions](M3k-RESULTS.md) and trusted-caller boundary
remain. AMD/NVIDIA hardware comparison and official spirv-val are unverified;
their absence does not block the documented Arc work. This is not all of P03
or general CUDA compatibility. Raw logs, generated assets and vendor binaries
remain ignored; public artifacts and commit identities are scanned.

## Independent review

An independent subagent reviewed bfb12bb..5c2c063 and the support documents,
approving the bounded change with no actionable Critical, Important or Minor
findings. It independently passed the three focused Rust tests and audited
400,000 Python signed/unsigned modular-oracle cases. It also checked the native
case counts, missing-write detection and upper64-bit input/output coverage.
This audit is separate from the implementer's actual GPU/regression runs.
The reviewer did not independently execute GPU smoke, reproduce the earlier
RED runs or establish official spirv-val/NVIDIA/AMD parity. Keep the branch as
a stacked draft on M3k; no merge.
