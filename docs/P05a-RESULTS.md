# P05a shared primary context results

Verified 2026-10-21 on Windows x64 / Intel Arc B390.
Clean candidate: `c783cbaaf42c4e61b62179cada8f6f6cc9fbf9aa`.
Execution-scope SHA-256:
`dbd068f1c552d2e74567d4020bafca737ff01ff7aa5af278e2c0fc3224c184ef`.
Later documentation commits do not relabel this native execution commit.

## Implemented

Three new exports provide shared, checked device-primary ownership:
`cuDevicePrimaryCtxRetain`, `cuDevicePrimaryCtxGetState`, and
`cuDevicePrimaryCtxRelease_v2`. Two threads can select the same primary context
and share its allocations and loaded modules. Retain/release never mutate TLS;
the final release invalidates resources. Ordinary contexts remain independent.

Only flags=0 are represented. Legacy release, reset and flag-setting exports are
unavailable. Stale primary handles return709; Destroy(primary) returns201 without
changing ownership. These are documented CT guards, not measured NVIDIA parity.
See the [design](superpowers/specs/2026-10-21-primary-context-design.md) and
[implementation plan](superpowers/plans/2026-10-21-primary-context.md).

## Observed validation

| Gate | Result |
| --- | --- |
| Required combined cases | 27/27 passed, clean source, no release claim |
| CPU Rust | 90 passed, two prepared tests excluded |
| Rust including prepared tests | 92 passed |
| Python | 60 passed |
| Official CUDA header ABI | 29 signatures and official-PFN calls passed |
| New independent consumers | Static import and dynamic loading, two threads each |
| New native numerical checks | 1,028 exact results and 256 guards |
| Existing Arc M3k–M3o | 2,304 cases, 19,372,800 exact results, 295,200 guards |
| Producer/validator | Five replays: two supported, three expected unsupported; eight positive and two corrupt validator controls |
| Original report bundle audit | Observed source/config/environment/catalog/tool/input identities matched |

The new consumers test initial/inactive state, bad devices/null arguments,
nonfinal release preserving modules and memory, final release from another
thread, stale TLS and module/function handles, explicit stale-stack recovery,
fresh activation, and ordinary-context isolation. Application and PTX bytes are
preserved through process-local bundles.

A preserved pre-feature DLL rejected the new dynamic consumer because the new
exports were absent. This is a local negative control, not a reconstructed
baseline source-build claim. Pure state tests inject creation failure and retain
overflow; an integrated release-helper test injects cleanup failure and verifies
inactive state, tombstones, quarantine, no retry and fresh activation. Actual
hardware failure was not induced.

Independent contract and whole-change reviews completed. Two material findings
were reproduced and fixed: multiline resolver extraction omitted two ABI ranges,
and stale-primary module failures left output handles uncleared. Focused
re-review reported no remaining Critical/Important finding in inspected code.

Raw reports remain ignored under `results/local/`. Vendor artifacts and local
paths are excluded; all 11 preexisting user files retain their saved hashes.
Hosted CPU/validator CI is separate evidence tracked on the draft PR.

## Remaining scope

P05b must define reset while retained, handle/resource generations, and release
after reset. P05c must address additional flags and independent library consumers.
The preexisting ordinary Destroy stack-removal policy is unchanged by P05a and
needs a separate conformance correction. Tombstones consume process-lifetime
metadata. General Runtime/library/framework compatibility, pinned allocation
APIs, AMD execution and NVIDIA behavioral comparison remain unverified.
