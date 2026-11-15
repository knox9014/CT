# R2k: primary ownership and retained activation

## Change

`crates/ct-cuda/src/primary_state.rs` now separates a stored primary handle from retained active usage. `get_or_create_unretained` obtains/reuses a handle without increasing references. A fresh reservation has references0, remains owned and reports inactive; later retain reuses the same handle and activates it. Releasing without retained usage returns201 without removing or retiring the reservation.

Public retain uses this helper internally and checks reference overflow before calling a factory. A failed factory publishes no new entry and preserves existing reference counts. Only this Rust file changes among the104 product files compared with the R2j checkpoint. No API export, resolver/table, version/profile, backend or header change is included.

## Evidence and limits

R2j observed the official Runtime reach private CUDART slot2, where the diagnostic callback denied the request. The pinned [reference implementation](https://github.com/vosen/ZLUDA/blob/08b19b28b7c334936846b3aeb61a43aef053e9a1/zluda/src/impl/driver.rs#L183) obtains the primary context without retain; its [test](https://github.com/vosen/ZLUDA/blob/08b19b28b7c334936846b3aeb61a43aef053e9a1/zluda/src/impl/driver.rs#L863) expects inactive state and identical handle on subsequent retain. These are reference-derived requirements, not official private ABI certification. [NVIDIA's public primary-context documentation](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__PRIMARY__CTX.html) documents activation on public retain and that retain does not push the context onto the calling thread's stack.

Independent design review identified an important distinction: reset can leave positive retained usage while removing its handle. Recreating a handle in that state can restore active status without adding usage. The helper is therefore called unretained, not inactive. A new test explicitly checks this existing CT state policy. Reset of a zero-reference reservation retires the old identity, preserves zero references and leaves another device untouched. Neither choice establishes NVIDIA's private reset/handle-lifetime semantics.

The helper is currently called by public retain; the fresh zero-reference reservation path is exercised directly by state tests and is not externally exposed. The state factory is abstract and may allocate native resources; API-inactive does not imply no native allocation. No private context service, pointer validation, Runtime forwarding or export-table support is connected in this phase. No new GPU execution or application success is claimed. Historical R2j captures remain bound to their original source; they are not presented as new-source evidence.

## Verification

Three tests were added before implementation; the focused test build failed because the required helper did not exist. After implementation and formatting, all9 primary-state tests passed. A fresh independent reviewer compared the file against R2j and ran all12 primary state/flags/cleanup tests successfully. The tests cover repeated lookup identity, zero-reference ownership, later activation, release rejection, creation failure, retained usage after reset, overflow, retirement and device isolation. Existing public retain/reset/release tests remain in the suite.

The private clean checkpoint passed the required CPU lane11/11: Rust212 with4 existing ignored tests, Python329 and Runtime129, plus formatting, Clippy, profiles/registry and publication checks. This is CPU/state evidence; no new native GPU run was performed. Final privacy/source checks are recorded in the ignored local final-verification record.

## Provenance and reproduction

- Source fingerprint: `5739c0eeda437a760f51108b715c89bd63a743bd32a4e2d8eeda5677ac033ff5`.
- Private checkpoint commit: `3a713bb8a4371b3e4c1e87c2ab26cce48b47da61`; tree: `3c5cd730d5669462a62d4e9784233585fa0e14f2`.
- Focused state check: `cargo test -p ct-cuda --lib primary_state::tests`.
- Related check: `cargo test -p ct-cuda --lib primary`.
- Clean checkpoint regression: `python scripts/run_validation.py --lane cpu --required --output-directory results/local/r2k-primary-cpu`.

Private source snapshots, build outputs and raw logs remain ignored local artifacts. No staging, root commit, upload, installation or managed-worktree edits are part of this phase.

## Next implementation boundary

The ownership distinction is a prerequisite for a real slot2 service, not that service itself. Next establish a bounded native-context adapter: output clearing, initialized/valid-device checks, stable owned handle, unchanged thread-local current context and clean teardown. Reset/release interactions of private handles need a separate evidence-backed policy before general forwarding. Hooks buffers and successful Runtime initialization remain open.
