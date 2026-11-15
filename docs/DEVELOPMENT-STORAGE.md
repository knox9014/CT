# Bounded local development storage

Development uses a bounded local working set and encrypted Google Drive archive units. Recovery keys stay only in the notebook's ignored `.local/ct-backup-keys` directory, as requested. Account data, credentials and recovery keys must never enter an upload selection.

Run `python scripts/cache_budget.py --reserve-gib 2` before clean CPU validation or a new native experiment. Defaults are a 40 GiB project `.cache` ceiling and a 30 GiB free-disk floor; the reservation is added before either check. `scripts/run_topology_attribute.py` reserves1GiB before its parent build. Historical R2r/R2t metadata runners require their matching immutable source before a fresh2GiB capture. The guard reads sizes only and never deletes files. Ordinary manual Cargo commands and older runners are outside these entry points' enforcement scope.

Use one dedicated `CARGO_TARGET_DIR` for a clean CPU candidate's root and nested Runtime workspaces, with `CARGO_INCREMENTAL=0`. After successful verification, retain the immutable source, private `.git`, validation configuration/report/toolchain records and logs, then remove only that dedicated CPU target. CPU target cleanup must be bounded to the newly created candidate and verified against its manifest; no root staging/commit or managed-worktree edits.

An accepted native run is a different retention unit. Its audit can reference its entire SDK tree, Driver target `.rlib/.rmeta`, bridge/provider/ABI outputs, all copied Runtime DLLs and observation records, plus pinned external compiler/Python/SDK archive identities. Retain that complete closure for the current accepted run. Do not remove a native run's target or SDK merely because it looks like a build cache.

ABI-only exception: when a saved auditor uses copied binaries, headers, observations and pinned external tools, and does not depend on the Cargo target, that target may move to cold storage after the complete encrypted unit has passed readback, full restoration and saved audit. Re-audit surviving local evidence after target removal. Record `binaries_and_observations_target_archived`; retain the complete target in Drive. This does not apply to the official Runtime context-bridge pipeline, whose `.rlib/.rmeta` and SDK closure remain required locally while it is warm.

For each new accepted phase:

1. Verify a private source candidate and clean CPU report, run fresh native children, then perform the saved consistency audit.
2. Build one small encrypted unit containing the immutable source/private Git, CPU reports and complete native run. Reserve enough headroom for encrypted output plus download readback without relying on compression.
3. Upload into the existing private CT Drive archive, read back every object, compare SHA256, verify all reconstructed file hashes and owner-only permissions. Publish the completion receipt last.
4. Keep current source, pinned tools and newest required evidence local. Reclaim verified transient upload/readback copies, the independent CPU target and the documented ABI-only target exception above. Older native units need exact receipt/dependency review before reclaim; failed runs remain labelled failed and count toward the limit. Cleanup must guard all ancestors of both recursive and file-unlink paths; persist a plan before removal and allow safe retry of partial removal without accepting changed or extra files. Keep metadata updates recoverable from that journal.

New units restore into a new empty staging directory using the provided `ct_archive.py` helper and the matching notebook-only key. Keep the source `.git` and native dependency tree intact. Verify source and artifact identities before using a restored run. A different tool installation/path may require separate reproducibility work; historical records must not be edited to manufacture a match.

The earlier 2026-10-31 monolithic cache archive supports whole-archive restoration with its existing helper. Selected-file retrieval from it is not implemented. Future small run/source units avoid requiring the full historical cache for routine retrieval. No background task or general-purpose synchronization service is installed by this workflow.
