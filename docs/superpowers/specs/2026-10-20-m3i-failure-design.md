# M3i: deterministic failure containment

User authorized the basic failure-injection check before further P03 expansion.
Base844a49a/M3h. Verify failure reporting, rejection of later work on a poisoned
context, and retention/no double-free when completion or cleanup is uncertain.
Do not reset a real GPU, alter system drivers, or claim automatic recovery.

## Approach

Compile a private fake Level Zero symbol provider only under cfg(test) in
ct-backend-intel. Production builds continue to import the real System32 loader;
no environment flag, public test API, new CUDA export or dependency is added.
The fake records calls and owns real host byte buffers for safe staging/copy
operations. Native return codes are injected at a chosen call occurrence. The
actual backend methods and ownership/control flow execute unchanged around it.

Cover launch append, argument/group setup, HtoD/DtoH append, synchronization,
staging free, kernel/module/list/context destruction and allocation failures.
Check call counts, returned errors, retained buffers/handles and untouched host
outputs. After poison, allocation/free/copy/load/unload/launch/synchronize/destroy
must not reach native calls. A separate synthetic context is independent; this
does not establish recovery after a physical driver reset.

Ordinary pre-submission errors (OOM, bad argument) return errors without poisoning
a healthy context. DEVICE_LOST0x70000001 and DEVICE_REQUIRES_RESET0x70000006
are fatal even before submission. Uncertain submission/completion/cleanup failures
retain the existing conservative poison policy. Add Context result observation
only where tests expose missing fatal handling. Mutable context arguments may
be necessary for allocate/free. Preserve original error, and test CUDA's native
error mapper separately: OOM->2, fatal/unknown->999; no full NVIDIA error parity.

## Limits and verification

Fake-return tests prove CT control flow and bookkeeping, not real driver fault
behavior, completion timing, actual OS loader retention or device-wide recovery.
Run test-first failures before any fixes, workspace/native-producer tests,
Python, lint and affected actual Arc M1/M2/M3h regressions. Keep26exports and
synthetic test code private to test builds. Fresh whole-branch reviewer and
publication/identity scans precede a draft PR stacked on M3h. Raw logs stay local.
