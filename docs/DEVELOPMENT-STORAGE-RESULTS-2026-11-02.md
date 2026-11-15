# Development storage results: 2026-11-02

R2r development and storage qualification completed. The public result is R2R-VIRTUAL-METADATA-RESULTS.md: CPU11/11 (Python354, Rust223 passed/7 ignored, Runtime129), fresh native24 children/47 deny checks and saved consistency audit passed. Explicit software-target attributes75/76 returned5/2 before the actual attribute15 refusal; default strict75 and production version refusal remain unchanged. Production Rust/tools/include files (115 selected paths) are unchanged from R2q.

The new native entry point checks cache + estimated2GiB peak <=40GiB and projected free space >=30GiB before starting its parent capture. Seven budget tests and eight virtual-prefix tests pass, including two RED-to-GREEN Runtime identity regressions. The guard is scoped to this new workflow, not every manual Cargo/legacy command.

Two independently restorable encrypted units were uploaded into the private CT Drive archive:

| Unit | Archive files | Logical bytes | Encrypted data bytes | Saved audit |
| --- | ---: | ---: | ---: | --- |
| Prior R2q | 1738 | 198597219 | 21947961 | 20 children |
| Current R2r | 1774 | 209051867 | 21949441 | 24 children |

Each includes immutable source and private Git objects, CPU reports and the complete native SDK/build/provider/observation closure. Neither excludes any required file. All transferred bytes were read back and SHA256 compared, every reconstructed file hash was verified, then the complete unit was restored and its source candidate and frozen saved audit were verified. These restored audits are consistency checks, not another GPU execution. The ten data/tool/guide files had owner-only permissions and correct parent folders; completion receipts were uploaded after verification.

The previous R2q native run's269 files/193204732 bytes were checked against the authenticated archive inventory, moved into bounded quarantine, checked again and reclaimed. Current R2r and pinned external tools remain local. Reproducible clean-CPU target output511685779 bytes was removed after its source/report verification. Transient archive/readback/restored copies3524 files/496064193 bytes were removed after successful recovery checks. Source, HEAD/index, protected11, current native dependencies and notebook-only recovery keys were retained.

The measured cache before this work was40131812085 bytes; after staging cleanup it was40150566843 bytes, a net increase of18754758 bytes (about19MB) while adding a new qualified run and immutable source checkpoint. Existing historical cache/tool data remains about37.4GiB; this work bounds further growth rather than claiming all historical data is gone. The next invocation still has the required headroom.

Private retrieval mapping is recorded in ignored `.cache/dev-storage/index.json`, with distinct `archived` and `working_backed` states, canonical Drive file references and key filenames (not key values). Keys remain only in the notebook, as explicitly requested. Mutable recovery-guide wording was updated to this policy; no USB/off-device key copy is requested. No background sync service, system driver replacement, root commit/staging/push or managed-worktree edits occurred.

Fresh independent final review found no Critical/Important findings. Deferred minor: the private one-off packaging helper creates an empty staging directory before its budget check; after budget refusal, bounded empty-directory cleanup is needed before retry. Completed units are unaffected. CUDA application/shipping support and the archive cryptography implementation itself were outside that review; current transfer/recovery and native evidence are reported separately.
