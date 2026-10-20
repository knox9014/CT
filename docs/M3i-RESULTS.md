# M3i: deterministic native-failure containment

Validated 2026-10-20. This is the basic failure-injection check before the next
P03 arithmetic slice, based on M3h844a49a. No real GPU failure or reset was induced.

## Changes established by failing tests

The initial fake-return run passed13 backend tests and failed3: fatal device
errors during kernel setup, memory allocation/free and module creation returned
errors but left the context usable. Shared result observation now poisons that
context on DEVICE_LOST0x70000001 or DEVICE_REQUIRES_RESET0x70000006, including
pre-submission operations. These constants were checked against the pinned
official Level Zero header already used by the native ABI checks.

Further RED->GREEN probes established two cleanup corrections. Any device-free
failure now poisons the context, preventing uncertain retries. Module build-log
cleanup failure retains the log handle, poisons the context and preserves the
original module-creation error if one already occurred. If creation already
reported a fatal device state, log destruction is skipped. Returned partial
module/kernel handles remain retained under the existing policy.

Ordinary allocation OOM and nonfatal kernel-setup argument errors do not poison
a healthy context. Uncertain submission/completion/cleanup failures still use
the conservative stop-and-retain policy. No automatic device recovery is added.
Native backend allocate/free now accept mutable Context so failure state can be
recorded; CUDA C signatures and26 exported symbols are unchanged.

## Failure probes

A private cfg(test) symbol provider returns controlled native codes while the
actual Backend methods execute. Thread-local state owns real host byte buffers,
records native calls and supports failure on a chosen call occurrence. The real
System32 loader import is used in normal builds. No runtime flag, environment
variable, public injection API, feature or new dependency was added.

[fault_tests.rs](../crates/ct-backend-intel/src/fault_tests.rs) contains15 new
failure/control tests. These supplement the four existing backend tests.

| Boundary | Verified behavior |
| --- | --- |
| Launch append |Original error returned, context poisoned, module/kernel/device storage retained |
| HtoD/DtoH append |Staging retained; failed DtoH does not publish unconfirmed bytes to host |
| Synchronization |Uncertain completion poisons; later cleanup is blocked |
| Staging/device free |Failure stops later native calls; retained buffers are not freed again |
| Kernel argument/group setup |Fatal LOST/RESET stops later submission; ordinary argument failure allows later launch |
| Device/host allocation |Fatal errors poison; ordinary allocation OOM allows later operations |
| Module creation |Fatal errors poison; ordinary OOM permits a later load |
| Partial kernel creation |Returned handles cleaned before module on ordinary failure; fatal failure retains them |
| Build-log destruction |Uncertain log retained; original error preserved; no cleanup call after known fatal state |
| Kernel/module destruction |Partial successes zeroed, remaining handles retained; no duplicate destruction |
| Context cleanup |Stops at failed list/free/context call; a previously freed allocation is never retried |
| Positive copy control |Correct byte round-trip, each successful staging buffer freed once |
| CUDA error mapping |Separate real mapper test: host/device OOM->2; fatal/unknown/NOT_READY->999; no failure maps to success |

After poison, probes check allocation, free, positive/zero-length copy, module
load/unload, launch, synchronization and context destruction fail without more
native calls. The keep-loaded flag is set. A second synthetic context remains
usable; this is context-local state isolation, not evidence of recovery after a
real device-wide reset.

The fake replaces the foreign-call boundary only in backend unit tests. These
are not end-to-end CUDA application failure injections. The CUDA mapper is tested
separately, and actual CUDA application success paths are checked on real Arc.
The real loader's OS unload behavior and actual native completion timing are not
established by the keep-loaded flag assertions.

## Actual checks

- Rust64 workspace tests including prepared ignored native/producer checks passed.
- Python19, rustfmt and all-target Clippy with warnings denied passed.
- Production DLL export table matched exactly the26 header symbols.
- Native ABI12 structures matched size/alignment/all field offsets.
- Actual Arc M1 memory/context and M2 kernel smoke scripts passed.
- M3h raw/compressed26 cases,37,394 outputs/4,856 guards and rejection/recovery passed.
- Independent official-header synthetic C consumer and public CLI passed936
  outputs/632 guards with application/input bytes preserved.

The pinned NVIDIA headers emitted the same two anonymous-struct extension
warnings during the C build. No new CT source warnings occurred. Generated/vendor
binaries, host paths and raw logs remain ignored; only CT/synthetic source and
sanitized evidence are public. See [M3h](M3h-RESULTS.md) for that workload's limits.

## Reproduce and limits

```powershell
$env:CARGO_INCREMENTAL = '0'
cargo test -p ct-backend-intel fault_tests
cargo test -p ct-cuda failure_mapping_tests
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py'
./scripts/check_level_zero_abi.ps1
./scripts/run_m1_smoke.ps1
./scripts/run_m2_smoke.ps1
./scripts/run_m3h_smoke.ps1
```

M3h native tests require the preserved baseline and pinned prerequisites documented
there. Failure probes themselves load no real GPU driver. Real driver loss/reset,
device-wide invalidation, actual loader unload, automatic recovery and complete
NVIDIA error precedence remain unverified. This is not full fault tolerance or a
general CUDA compatibility milestone; P03 arithmetic/ABI expansion is still next.

## Independent review

A fresh-context whole-branch reviewer found no actionable findings and
independently passed25 backend/CUDA library tests. The reviewer inspected existing
native evidence rather than rerunning the full GPU matrix.

Context startup failures before commands/allocations exist are not exhaustively
covered by this provider. Local metadata/current-context APIs may still work
after poison, but cannot bypass backend submission guards. A successful DtoH copy
may have published confirmed bytes before later staging cleanup fails; no
transactional host-output guarantee or universal sticky-error parity is claimed.
Physical driver failure, device-wide invalidation, real loader unloading and
automatic recovery remain separate unverified work.
