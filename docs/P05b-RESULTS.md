# P05b primary reset results

Verified 2026-10-21, Windows x64 / Intel Arc B390.
Clean candidate `f6d41cdc4fe6dea3ca02b89f90f6147261bbe1c4`.
Execution-scope SHA-256:
`4cf07098eea122a5062bf7aeeb54db22a7262da8e806ee83166de8ddbe4003b8`.
Subsequent documentation commits do not relabel this native-tested source.

## Behavior

`cuDevicePrimaryCtxReset_v2` now deactivates primary resources without consuming
retained usage. Reset never edits TLS. Outstanding releases remain valid; a
successful new retain explicitly creates a fresh active generation and increments
the preserved reference count. Repeated inactive reset does no native cleanup.
Creation failure/overflow preserves usage; cleanup failure quarantines uncertain
resources without retry. Ordinary contexts remain independent.

The resolver selects v2 only for canonical Reset requests11000–12000; no legacy
Reset export is advertised. Only default flags are represented. See the
[design](superpowers/specs/2026-10-21-primary-reset-design.md),
[plan](superpowers/plans/2026-10-21-primary-reset.md), and
[Driver contract](compatibility/driver-api.md).

## Observed validation

| Gate | Result |
| --- | --- |
| Clean required combined cases | 28/28 passed; release_claim=false |
| Rust CPU | 94 passed, two prepared cases excluded |
| Rust including prepared cases | 96 passed |
| Python | 61 passed |
| Official CUDA header ABI | 30 signatures and official-PFN calls passed |
| New reset consumers | Static/dynamic ordinary loading; two threads each |
| New numerical checks | 1,028 exact results, 256 guards |
| Existing primary consumers | P05a static/dynamic sharing and final release passed |
| Existing Arc M3k–M3o | 2,304 cases, 19,372,800 exact results, 295,200 guards |
| Compiler/validator | Five replays: two supported, three expected unsupported; eight valid and two corrupt SPIR-V controls |
| Original report audit | Observed source/config/environment/catalog/tool/input identities matched |

The reset consumers execute a kernel before reset, coordinate a second thread's
outstanding retain/release, check both unchanged TLS stacks and stale module/
function handles, reactivate with remaining references, and execute a new kernel
after two further releases. Repeated reset and final inactive release are checked;
ordinary memory survives throughout. Application and PTX bytes are unchanged.

A preserved local pre-reset DLL rejected the new dynamic consumer because Reset
was absent. This is an artifact negative control, not a reconstructed source-build
claim. Pure state tests cover failure, overflow, no-op reset and device isolation;
the actual generic reset/release helpers inject cleanup failure and verify
quarantine, inactive ownership, preserved usage, no retry and fresh activation.
Real device failure was not induced.

Independent contract and whole-change reviews found no actionable material
implementation issue in the inspected scope. Publication/identity checks passed;
all11 preexisting user files retain saved hashes. Raw reports and vendor/generated
artifacts remain ignored. Hosted CPU/validator CI is separate evidence on the PR.

## Limits and next step

Old CUcontext handles remain stale709; callers explicitly reacquire/select after
reset. Exact NVIDIA post-reset identity/GetCurrent behavior is unverified. This
policy can constrain consumers that reuse old context values. Native device
addresses may be reused after deallocation; stale raw pointer generation safety
is not claimed. Tombstones use process-lifetime metadata.

P05c additional flags and independent library consumers remain next. Legacy
primary ABI, the preexisting ordinary Destroy stack policy, pinned-memory APIs,
asynchronous/Runtime/framework/library support, AMD and NVIDIA comparison remain
outside this bounded reset result.
