# R2f explicit export-query rejection experiment

**Goal:** Observe the actual public export-table calls and propagation of801 after real initialization, without providing a successful private table. Independent read-only design review accepted the following bounded v2-only intervention.

**Architecture:** Separate diagnostic subclass, worker and validator. Production Driver/exports/version remain unchanged. Reuse the R2d guarded worker via explicit optional hooks whose defaults preserve existing behavior. Existing raw lookup remains null and old4arg resolver remains500/null. Only5arg resolution for cuGetExportTable/3000/flags0 can present a callback, after recording actual0/null and optional status1. Pointer presentation/status1-to0 are labelled interventions. Keep inner/outer/export callbacks alive through restore and unload.

The callback clears valid output storage, returns1 for null arguments without reading UUID, otherwise reads exactly16 valid bytes and rejects with801. Only the two observed IDs are allowed; unexpected IDs/preconditions/failures latch and invalidate the child. Expected rejection is not a kernel guard. No fabricated successful table.

- [x] Add failing tests for v2-only presentation, actual/presented metadata, callback output/null/read/failure contracts, preserved raw/old routes and finite outcome/order gates.
- [x] Implement `scripts/export_reject_observer.py`, `scripts/export_reject_check.py`, `scripts/export_reject_worker.py` and default-preserving hooks in `real_bootstrap_worker.py`. Add official public-header type assertion in `tests/export_reject_abi.cpp`.
- [x] Run native contracts before Runtime samples. Capture before nominal/faithful controls, existing20 guard contracts plus export contracts, ordinary direct Driver, existing missing-export samples and new reject samples, then after controls. Stop immediately on unexpected status/order, guard/failure, drift or fault.
- [x] Require early f8cff95121468b4eb9e2fb469e7c0dd9 rejection, actual version801/output0, labelled fixed sample, actual init0, post-init6bd5fb6c5bf4e74a8987d93912fd9df9 rejection, Runtime801/count−1. No count calls. Existing no-export samples remain36.
- [x] Independently review final changes; run focused/full CPU validation in a private clean checkpoint, saved capture integrity recheck, privacy/protected-file/HEAD/index verification. Report diagnostic scope only.

Ruling: use the existing primary working copy with private source checkpoints and ignored local bundles; preserve accepted worktrees, dirty changes, protected files and root index. Do not stage, root-commit, upload, install or run application kernels.

## Outcome

Both original-surface samples returned36; both explicit-rejection samples made the two expected queries and returned801 after actual init0. Thirteen children, the31-check extended native contract and the clean full CPU11/11 lane passed. Independent final review completed with no remaining blocker. See `docs/R2F-EXPORT-REJECTION-RESULTS.md`. Private table contracts and application support remain unresolved.
