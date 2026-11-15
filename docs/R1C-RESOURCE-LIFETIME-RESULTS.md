# R1c: bounded resource lifetime and retirement

Status: R1c completed2026-10-28. Implementation, independent review, clean CPU qualification and fresh full capture/separate replay passed. This is bounded single-thread resource-reuse qualification, not an hours-long soak, whole R1 or a zero-leak guarantee.

Single-thread/`worker_threads=1` means one host API caller per worker process. Runtime copy-worker and backend/driver internal threads are not counted by that field.

## Closed Runtime path

Two seeds193,731 each run256 cycles in one process. Each cycle creates two pinned host buffers, two device buffers, an owned stream(flag0/1) and one event recorded twice. It enqueues H2D, frees the source host buffer before explicit synchronization, launches an actual nvcc kernel and copies full A/B buffers to pinned host output. The selected completion API alternates between event synchronization, stream destruction and device free. An event synchronization also precedes raw-array inspection in every mode; these are integrated cleanup sequences, not isolated timing proofs of each fence. All32 input/output words and all6 device/host destination guard words are externally inspected per cycle.

The native consumer checks API contracts and emits raw arrays; it does not decide numerical success. Python independently recomputes every result. Recoverable errors each cycle include invalid flags1, pageable async copy801, immediate duplicate host/device free1 and stale stream/event synchronization/destruction400. Duplicate raw-pointer checks occur before another allocation can reuse the address. First logical stream/event tokens must remain stale after replacement allocations.

Each process also fills128 live streams and128 live events, requires creation129 to return801, destroys the live set, and creates/destroys replacements successfully. Successful stream/event tokens remain below the4096 cumulative lifetime ceiling. This proves the tested live-budget recovery, not reclamation of every hidden allocator/driver cache or all memory leaks. The Runtime primary context and one live static kernel registration persist by design; dynamic Runtime registration unload/reset are outside this scope.

Free-before-explicit-sync does not establish that work was still pending when free began. Deterministic controlled Rust tests exercise blocking leases; this native workload does not claim physical overlap or blocking-duration proof.

## Separate Driver path

Two isolated Driver workers each repeat160 module loads/launches/unloads in one context, crossing the128 live-module ceiling cumulatively while keeping only one module live. They consume the fixed synthetic vector PTX, not the original matrix EXE. Changed PTX is rejected before Device creation. Each cycle checks a failed-name lookup500, correct launch, full A/B/C readbacks and16 guard words on each side of every buffer. It then requires duplicate unload, stale function launch and stale module lookup to return400, frees all device allocations and checks one immediate duplicate free1. Context cleanup runs on exit/rejection.

Runtime and Driver workers are separate processes; no new Driver/Runtime context-sharing contract is inferred. Runtime uses a separate `lifetime-runtime.dll` copy pinned to the parent's nominal `matrix-runtime-original.dll`; earlier parent artifacts are not overwritten or silently substituted.

## Controls and fixed validation

Nine closed observations: two positive and two omission workers per path, plus one Driver no-unload worker. Omission workers run8 cycles with all API checks intact; external numerics must fail with the specific no-launch/no-copy signature. The no-launch proxy preserves stale-call validation. A no-unload proxy must produce controlled exit42/reason `duplicate_unload`, with context cleanup attempted before reporting rejection. No nominal CT code uses these macros.

Compiler preflight built the CUDA consumer and3 control DLLs. Short native8-cycle smoke tests passed all7 path/control modes; these used earlier providers and are preflight evidence only. Formal qualification requires the fresh source-bound parent/capture/replay below.

Frozen product fingerprint: `d28b4fe2b6f4ae42071e13d2248c2343efd69c72b15d3fb1b412a21a75cca8aa`. Private checkpoint commit: `187cb5dccfc77d233d00a53e98ca55ba93b379fc`; Git tree: `2a8bfa173e8a38057a99b2c2755bb27c8b6be2c0`; file-map SHA256: `605fd76f91e7688644f83664af51ec46bd5f84c83c2436d81d56d0bbe544cbab`. Source excludes ignored SDK/cache/binaries; installed host tools/dependency caches remain prerequisites.

Clean CPU11/11 passed with `clean=true`, Python262, Rust207/4 existing ignored and Runtime129. All10 focused lifetime tests passed, including fake completion, relabelled omission data, scalar/type/guard/counter corruption, missing observations, source/parent/provider/profile drift and changed PTX preflight. Independent read-only review found no actionable defect and clarified the free-before-explicit-sync limit.

The tested checkpoint predates ordinary result/plan reporting edits. Those edits do not change the product fingerprint. Original index/HEAD/protected11 bytes are checked at final acceptance; no root stage/commit/push or upload is performed.

## Intel acceptance

Fresh existing-app/R1a/R1b parent capture passed under the same frozen source. All9 lifetime observations passed their defined expectations. Per pass, positives cover512 Runtime cycles and320 Driver module cycles,26624 arithmetic output words,36864 preserved input words and33792 guard words (97280 raw words total). The positive API records include3012 stale-handle rejections,2688 recoverable-error rejections,4 live-budget rejections and4 successful replacement allocations. These are operation counts, not independent application diversity.

Four omission workers completed their API checks but all32 omitted-operation cycles were rejected numerically with the expected signature. The no-unload worker was rejected with exit42/reason `duplicate_unload`. Separate replay reexecuted all9 observations in fresh processes and matched every raw observation hash and exit code. Replay does not add new input coverage.

Capture SHA256: `4cff73afd11f3df5e9bded9ea07dec90e72ff489a5a80022ef943b0314962e2a`. Replay SHA256: `f4be5d5210339ecaab02f21dfa388278f65245509258ff0f6c6fe7bf2f43d02f`. Raw evidence remains ignored; final cross-check is recorded in `.cache/r1c-final-verification.json`.

## Remaining scope

Concurrent host calls, actual device loss/recovery, in-flight native module unload, reset/interop, exhaustive cumulative lifetime budgets, arbitrary application workloads, other Intel PCs, performance and AMD remain unqualified. Whole R1 remains incomplete.
