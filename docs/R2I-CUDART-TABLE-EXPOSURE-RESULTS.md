# R2i: bounded CUDART table-pointer exposure

## Result

Official Runtime12.9.79 accepted the explicitly diagnostic CUDART table pointer in the observed startup path and then made the next expected export-table query. Both fixed version-presentation samples followed the same sequence:

1. Early `f8cff95121468b4eb9e2fb469e7c0dd9` query rejected801.
2. Actual CT version801/output0, followed by a separately labelled presentation12000 or12090.
3. Actual cuInit(0) returned0.
4. Post-init `6bd5fb6c5bf4e74a8987d93912fd9df9` query received0 and the authenticated104-byte CUDART deny-table pointer, labelled as an intervention.
5. Next `a094798c2e742e7493f20800200c0a66` query was observed and explicitly rejected801.
6. Runtime returned801/count−1, without an observed device-count call.

This advances the observed diagnostic prefix to the hooks-table query predicted by R2g static evidence. It is not Runtime enumeration or application success. No hooks table/buffer was exposed, no private function performed an operation and no shipping version was authorized. The production Driver version response remains801/output0.

## Pointer and lifetime boundary

The new subclass retains the existing v2-only labelled resolver presentation; raw lookup and the old4arg resolver retain their original behavior. It does not broaden the base rejection class's identifier set. Only the exact post-init query can receive a table address. Null requests return1 without UUID reads and latch failure; unknown IDs/order/preconditions invalidate the child. No generic private table is manufactured.

The fixture must first pass its standalone Rust3/C++47 proof. The child authenticates that capture, the copied/loaded DLL and source/artifact identities, then checks table storage bounds/alignment,104-byte metadata, zero holes and in-image callable addresses. All private callbacks in the fixture remain typed deny operations. The observer does not call any of them.

Fixture mask/stop state was0 before exposure, at IAT restoration after the Runtime call, and after Runtime unload. Because the mask is monotonic and has no reset export, these observations also rule out a hidden earlier fixture hit in this prefix. Any nonzero mask invalidates the child even if no later Python wrapper runs. Wrapped forwarding additionally consults this latch; it is not a complete native-call sandbox.

The fixture stays loaded through Runtime IAT restoration and unload. Final fixture state is read before freeing it; afterward only module absence is checked. Both Runtime and fixture unload checks passed, and callback references remain alive through Runtime teardown. Controls use the original missing/rejection paths; the diagnostic exposure additionally loads the fixture and observes its state. No broader causal or compatibility claim is drawn from those instrumentation differences.

## Validation

The fresh pipeline passed17 bootstrap children: the original13 missing/rejection/control children, two CUDART exposure children and final faithful/nominal controls. It also passed the preceding standalone fixture's Rust3 tests and C++47 direct checks. The original direct Driver control still enumerates one Intel device. Normal arms had zero public guard hits/callback failures; both exposure arms had private mask0 throughout, and final controls matched their original counterparts.

Seven focused Python tests cover layout/target bounds, finite query order, null handling, latch blocking, restoration after state-query failure, outcome metadata and missing fixture identity. Existing bootstrap/rejection tests passed again. The clean private checkpoint passed full CPU11/11, including Python324, Rust209 with4 existing ignored tests and Runtime129, plus formatting, Clippy, profiles/registry and publication checks.

Independent design, implementation and final saved-evidence review completed. Review tightened fixture identity checks and immediate per-child provider/Runtime identity checks before advancing. The final review was a consistency audit, not another native execution. Production Rust/Cargo/include bytes remain unchanged.

## Provenance

- Source fingerprint: `4dbcc109311628e2a07b104eff48f4b058a26eb45b35ca2014e81f35c277e5f0`.
- Private clean checkpoint commit: `6b6683c6ff9d124be6d350c38afa5045bf5b8f13`; tree: `824e9a215f39534588752102f82964af54366bf0`.
- Local bootstrap capture ID: `7540cdeb54064bd082812c715c3908f0`.
- Exposure capture SHA256: `f748b0f884a3af27170b3479fe3daf50c29f6ba4c9f3645bc2902be439c176cb`.
- Saved recheck SHA256: `855391c2a50258e8d9f81550b9bfec5332ef7cf1bc7e2d92ec699bd7161b07df`.
- Fresh CT DLL SHA256: `0a218b0d2c8ad4acf7042b5aff6ab7555f49998c77c51b6283b0e1df0f80b085`.
- Fresh fixture DLL SHA256: `41eb4b0ae16a83b427119c5fb9e3eb784e91e68e445c635725ff684a4564089d`.
- Fixture capture SHA256: `4264b86cee86fe636dde3a1f9aab3f3943e2aa78f25c768eb7679fa331a4e6b1`.
- Pinned Runtime DLL SHA256: `760c38928bbe5759f7b31ed6692599eb7ec83cedd5702e84c2b72028a89837e1`.

Saved recheck validates local source/artifact/observation consistency, not external attestation or another native run. Raw logs, SDK/source caches, binaries, environments and absolute paths remain ignored local artifacts. No root staging/commit, upload, installation or accepted-worktree edit was performed. Local final verification separately records privacy/protected-file/HEAD/index checks.

## Reproduce and next work

Run `python scripts/run_table_exposure.py` with the existing pinned local setup. It accepts explicit `--python`, `--archive` and `--source-root` overrides. Use `--recheck <local-bootstrap-capture-folder>` for saved consistency checks.

The next actual boundary is the hooks query. A separately reviewed experiment must distinguish exposing its deny-only layout from providing any real callback-buffer service, retain exact void signatures and pointer lifetimes, and stop at the first private hit or unsupported condition. Do not invent buffers/semantics to force a success result. Useful application execution, truthful compatibility/version profiles and Intel release qualification remain open.
