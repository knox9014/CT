# P05c default flags and independent library consumer results

Verified 2026-10-21, Windows x64 / Intel Arc B390.
Clean candidate `cf695064331f091be35cf0363d0a4029501e501b`.
Execution-scope SHA-256:
`4f7c0c213985263f4efe49eda7a95659c766cf01e3528453e7601a11a5d35a9f`.
Later documentation commits do not relabel the native-tested candidate.

## Implemented scope

`cuDevicePrimaryCtxSetFlags_v2` accepts default flags0 without activation or
resource/reference/TLS changes. Recognized nonzero flags return801; unknown bits
or combined scheduling flags return1. `cuCtxGetFlags` returns0 for valid current
contexts,201 for absent context and709 for stale primary context. Legacy setter
is absent. Official ABI floors are11000 and7000, within the existing12000 ceiling.

Two separately compiled, CT-owned DLLs use only official CUDA declarations.
Producer statically imports CUDA, creates allocations/module/kernel and retains
the primary context. Consumer dynamically resolves official PFNs and independently
retains the same context. All three modules observe the same application-local
driver. After explicit producer release and actual DLL unload, consumer still
executes using shared resources. Final consumer release logically invalidates the
primary handles; fresh activation/reset and ordinary context isolation pass.

See [design](superpowers/specs/2026-10-21-primary-consumers-design.md),
[plan](superpowers/plans/2026-10-21-primary-consumers.md) and
[Driver contract](compatibility/driver-api.md).

## Observed validation

| Gate | Result |
| --- | --- |
| Clean required combined cases | 29/29 passed; release_claim=false |
| Rust | 95 normal;97 including prepared cases |
| Python | 62 passed |
| Official header ABI | 32 signatures, flag/error/query values and official-PFN calls passed |
| New library consumer | Two DLLs,514 exact results,128 guards |
| Deliberately skipped second launch | Rejected at execution2 numerical check |
| Existing Arc M3k–M3o | 2,304 cases,19,372,800 exact results,295,200 guards |
| Prior consumers | Driver connection, P05a sharing and P05b reset passed |
| Producer/validator | Five replays: two supported, three expected unsupported; eight accepted and two corrupt controls |
| Original bundle audit | Observed source/config/environment/catalog/tool/input identities matched |

Each normative execution changes input and resets output before launching, so
old results cannot substitute for execution after DLL unload. Independent review
found this stale-output gap; a deliberately broken separate consumer initially
slipped through, then the corrected test rejected it with the execution2 numeric
diagnostic. Focused re-review reported no remaining material finding.

PE imports and actual unload are checked, and host/DLL/PTX bytes remain unchanged
inside explicit test bundles. A preserved local older CT DLL rejected the new
flag exports; it is an artifact negative control, not a source-reconstructed
baseline claim. No independent native-deallocation or device-failure proof is
inferred from stale-handle checks.

Publication/identity scans passed; all11 original user files retain saved hashes.
Raw reports, generated DLLs and vendor headers remain ignored. Hosted CPU/
validator CI is separate evidence tracked on the stacked draft PR.

## Remaining boundaries

This is a partial P05c result. Nondefault scheduling remains unsupported because
the synchronous immediate-list backend waits inside append calls. Flags0 means
CT's existing default policy, not NVIDIA AUTO heuristic parity. Deprecated
MAP_HOST/LMEM hints remain unsupported; mapped/pinned/local-memory support is not
established. Test-only DLL copying does not add public automatic dependency
packaging or third-party CUDA library/framework support.

P05b fresh-context generation, stale709 and native raw-address reuse limits remain.
The preexisting ordinary Destroy stack policy still needs a separate correction.
Next work can address that context conformance gap and P06a D2D/memset/property
APIs; nondefault waits belong with the later execution-model work. AMD/NVIDIA
hardware execution and broader Runtime/library compatibility remain unverified.
