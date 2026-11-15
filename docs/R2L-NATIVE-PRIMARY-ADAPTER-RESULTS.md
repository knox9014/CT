# R2l: internal native primary-context adapter

## Result

One explicit native Rust test passed on the selected `Intel(R) Arc(TM) B390 GPU`. It connects R2k ownership state to CT's real Level Zero context factory and normal cleanup. Fresh unretained acquisition creates an owned handle while primary state remains inactive, repeated lookup reuses it, and retained acquisition activates the same handle. Unretained lookup of the active handle does not add another reference; one final release removes and retires it.

The test also creates a separate ordinary native context and installs its handle on the local calling thread's stack. Acquisition, release and reset preserve that stack; a restoration guard restores the original stack and the test asserts it explicitly. Normal successful completion leaves CT's owned-context map and retired/quarantined-context vector empty. This checks CT's tracked lifecycle and successful cleanup returns; it is not an external GPU-driver leak audit.

This is an internal native adapter test, not official CUDA Runtime execution or a successful private slot2 service. No private export table, new public export, version claim, compatibility profile or header is added. Historical R2j observations remain bound to their original source.

## Code and bounded policy

The only product deltas against R2k are `crates/ct-cuda/src/primary.rs` and `primary_state.rs`. The internal acquire_primary helper validates null output, clears a valid output before initialization/device errors, then delegates to existing transactional ownership creation. Public retain retains its previous initialization-first wrapper, preserving its prior output/error ordering. No acquisition operation changes TLS.

Unretained release at references0 returns201 and leaves its native context owned. Reset of a reservation retires and cleans it. The state predicate has_pending_usage identifies positive retained usage with no owned handle after reset. An unretained adapter request in that state returns801 with null output before allocation; the native test confirms unchanged next handle counter and owned-context map. Public retained acquisition retains CT's existing recreation policy. This conservative rejection avoids asserting unverified private reset/identity semantics.

The native test uses a local Runtime and does not pass its handles into public functions backed by the global Runtime. It checks negative and out-of-range ordinals clear output, empty/nonempty current stacks, stable identity, active lookup reference behavior, reservation release/reset and final cleanup. CPU tests check null/uninitialized output behavior and pending usage transitions, including failure and device isolation. Existing generic cleanup-failure tests continue to cover quarantine and no-retry policy.

## Validation

Tests were added first; the focused build failed on missing acquire_primary/has_pending_usage. After implementation and formatting, related CPU tests passed14 with the hardware case intentionally ignored. An independent reviewer ran that same CPU group successfully and reviewed the native test before hardware execution.

The native test was then run alone in a fresh process from a privacy-scanned clean checkpoint, with a separate fresh build target, exact test-name selection, ignored-tests enabled and one test thread. It passed1/1 in0.06 seconds of test execution; this is not a performance benchmark. The device name is captured from the selected Backend device, not inferred from old environment notes. Native log and capture identities were independently checked against the frozen source without rerunning hardware.

The clean checkpoint passed the full required CPU lane11/11: Python329, Rust214 with5 ignored tests, Runtime129, formatting, Clippy and registry/profile/publication checks. The5 ignored Rust tests include the new native case and4 pre-existing ignored cases. The new native case passed separately as described above. Final privacy/protected-file checks are recorded in the ignored local final-verification record.

## Provenance

- Source fingerprint: `0a9f6a474733b54f11a2d6cc96a0e3efa881b339d5963e2a889ce0772fa29189`.
- Private checkpoint commit: `0c99378923ed8a7cea9f9a63700c182b91cd1482`; tree: `b79e8da84c336ba6c7cd182edb0360e9b31445cb`.
- Native capture SHA256: `98eadff6cd30b1e9a9a0bc21ecf95f9bd6e7ad30636d39e889538a05a85b462b`.
- Native log SHA256: `dcc96fad16766a460ef0387c18113ca1bbeddae1ff010130d8899bf37f120694`.

Local capture includes the exact command, checkpoint/source identity, observed device, compiler identity and native log hash. It is reproducible local evidence, not external attestation. Raw logs, commands containing absolute paths, binaries and source checkpoints remain ignored. No root staging/commit/upload/install or managed-worktree edits were performed.

## Reproduction and next boundary

Related CPU check: `cargo test -p ct-cuda --lib primary`.

Explicit native check on a supported Intel machine:

```text
cargo test --locked -p ct-cuda --lib primary::tests::native_unretained_primary_preserves_tls_and_cleans_resources -- --ignored --exact --nocapture --test-threads=1
```

For a clean source checkpoint run the required CPU lane separately and capture the native command/log in ignored local results. Missing hardware or failed native assertions are failures for the explicit native check, not automatic passes.

Next connect a separately reviewed private slot2 callback to this internal adapter with exact signature, output and ownership rules, retaining the pending-usage refusal. Prove DLL/table/callback lifetime and a finite guarded Runtime prefix before general exposure. Hooks getter buffers remain unimplemented; useful CUDA application execution remains open.
