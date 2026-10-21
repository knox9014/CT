# Ordinary context destruction correction

Verified 2026-10-21, Windows x64 / Intel Arc B390.
Clean native-tested candidate: `17206815ca5c96b8326b03edf600b608c7a4a5a9`.
Execution-scope SHA-256:
`c2e192e8cfd51b81ffe155983905ec3ab2b8d6fb5af643065ac00e925a7b6726`.
Later documentation commits do not relabel this candidate.

## Behavior

Previously, ordinary `cuCtxDestroy` removed every matching entry from the
calling thread's stack, including buried duplicates and noncurrent entries.
It now pops exactly one top entry only when the destroyed context is current.
Buried entries and other threads' stacks remain unchanged. Destroyed ordinary
IDs are tombstoned before cleanup; subsequent context use returns709. Unknown
IDs and an absent current context remain201. Primary context destruction still
returns201 without mutating its state. No API exports were added:32 remain.

This follows the stack and other-thread destruction rules in the
[CUDA12.0.1 context contract](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-driver-api/group__CUDA__CTX.html).
See the bounded [CT contract](compatibility/driver-api.md).

## Validation

| Gate | Observed result |
| --- | --- |
| Clean required combined lane | 30/30 passed; release_claim=false |
| Rust | 97 normal;99 including prepared cases |
| Python | 62 passed |
| New official-header native consumer | Three cases, two threads, three surviving-context memory checks |
| ABI | Existing32 signatures and official-PFN calls passed |
| Existing native/producer/validator regression | All required cases passed |
| Independent bundle audit | Clean source, execution fingerprint, configuration, environment, tool and input identities matched |

The unchanged native application tests duplicate stack entries, destruction of
a buried context, and a different thread's stale context. The threads coordinate
so no GPU operation races destruction. Each scenario also verifies memory owned
by the surviving context. A preserved older local DLL failed specifically with
`duplicate stack entry was removed`; its SHA-256 was
`e915e121125cc88d077a2458120f57631b34ff7a5c666db66ce6f3040ec2a68b`.
That is an artifact negative control, not a source-reconstructed baseline.

Two new Rust tests cover stack mutation and destroyed-versus-unknown handle
classification. Independent read-only review reported no material finding in
the inspected stack, primary guard, tombstone, cleanup and native test paths.
Publication/identity checks passed and all11 saved original user files retain
their hashes. Raw reports, vendor headers and generated binaries stay ignored.
Hosted CPU/validator CI is separate evidence tracked on the stacked draft PR.

## Boundaries and next work

Exact NVIDIA parity for `cuCtxGetCurrent` on an already destroyed current
handle and arbitrary repeated stale-handle queries remains unverified. CT's
documented deterministic guard returns709 and clears pointer outputs where
specified. Tombstones retain process-lifetime metadata. Native cleanup failure
uses the existing quarantine path; these tests do not independently establish
device-failure recovery or physical native deallocation.

[P05c](P05c-RESULTS.md) remains partial: nondefault scheduling and real external
library consumers are outstanding. Next is P06a D2D/memset/property contracts and
implementation. General cudart/framework support and AMD/NVIDIA execution remain
unverified. This correction does not establish universal CUDA compatibility.
