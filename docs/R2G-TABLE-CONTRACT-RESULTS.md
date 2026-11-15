# R2g: checked public table declarations and next implementation boundary

## What changed

Added an offline inventory in `docs/compatibility/bootstrap-tables.json` and `scripts/check_bootstrap_tables.py`. It checks table identity, metadata versus callable slots, null holes, exact parameter/return types, calling convention, byte sizes, count units and pinned source identity. It always reports native success authorization false. No Driver implementation, public export surface or successful private table was added.

The investigation used two primary source files at ZLUDA commit `08b19b28b7c334936846b3aeb61a43aef053e9a1`, not an unpinned branch snapshot:

- [Declarations](https://github.com/vosen/ZLUDA/blob/08b19b28b7c334936846b3aeb61a43aef053e9a1/dark_api/src/lib.rs#L226): the observed6bd5 identifier is named CUDART_INTERFACE with13 slots, including byte-size metadata and seven declared functions. The a094 identifier is a separate seven-slot hooks table with void getters at indexes2/6. Function signatures differ; public module-load guards do not cover private module-loading entries1/6/8. Undeclared slots remain null in this implementation.
- [Implementation/reference behavior](https://github.com/vosen/ZLUDA/blob/08b19b28b7c334936846b3aeb61a43aef053e9a1/zluda/src/impl/driver.rs#L243): the getters return persistent u32 buffers and element counts1024/14. The same file's context test requires an inactive context for a private operation; ordinary retain is not an established substitute.

These are third-party declarations and reference behavior, not an official NVIDIA ABI or proof of CT compatibility. Source implementation text remains in ignored local storage; the public inventory contains derived interface facts and links.

## Runtime evidence, kept separate

The pinned Runtime12.9.79's immediate path stores CUDART_INTERFACE at object field0x90, then queries the hooks identifier `a094798c2e742e7493f20800200c0a66` into field0x98. Helper22d60 loads that second table and calls offsets0x10/0x30. Those are hooks slots2/6, not CUDART slots2/6. Field offsets from unrelated objects are not interchangeable evidence.

Static instruction checks prove comparisons of the getter-reported counts to487/14. They do not prove an official element-count ABI or the broader buffer meaning. Accordingly the inventory separates `runtime_min_reported_count` from `source_count_unit`, marks these Runtime facts static-only and leaves dynamic-observation/buffer-meaning flags false. Nine instruction assertions and the16-byte hooks identifier were checked against the authenticated local Runtime/disassembly identities. No new Runtime calls or successful table exposure were executed in R2g.

## Validation and evidence

Five new focused tests reject concrete ABI mistakes: calling slot0 or null holes, wrong table/offset, void versus status return, arity/convention errors, pointer-depth changes, byte/element confusion and altered/missing source evidence. Source verification checks cached file hashes and normalized Rust declaration types against the inventory. Independent read-only research and implementation review completed; count-unit wording and canonical name/effect validation were corrected before the final review.

The private clean checkpoint passed the full CPU11/11 lane, including Python315, Rust209 with4 existing ignored tests, Runtime129, formatting, Clippy, profile/registry and publication checks. The original production Rust/Cargo/include bytes and root HEAD/index remain unchanged. This phase adds no native GPU test result; previous R2f observations retain their original source/capture identities.

- Product-source fingerprint: `e5b82360c953c636586cda83dbc52e5aa907c56c386cde8219cda1f76099cfcc`.
- Private checkpoint commit: `c5f2db7271e9528cb63361dcfc4e19e7202e5d2b`; tree: `b13c255957a4f36cf5522a8bdc03cc0c234a0c96`.
- Inventory SHA256: `80ca287761fa1863b52df5b7828a8e261609499a1d2c78c9858ac27c77541c02`.
- Cached declaration UTF8 SHA256: `e1c4a6ce02631ec13b2be7f08c9c4682492bf42ed065739ca0777810f0fc47bf`.
- Cached reference implementation UTF8 SHA256: `49a76ea0a43369ccbf122a9a1dec20a2f1abdd7cbdaaa8201350082808e8ca69`.
- Pinned Runtime DLL SHA256: `760c38928bbe5759f7b31ed6692599eb7ec83cedd5702e84c2b72028a89837e1`.
- Local disassembly SHA256: `92309a11965cacaf1384316f3b89b2cf19a514f1fe4a3cae37d1c2e3812a18fb`.

Cached UTF8 hashes identify the local evidence text, not Git blob identities. Raw source bytes, disassembly, DLLs, environments and absolute local paths are ignored and unpublished. No staging, root commit, upload or installation was performed. Privacy/protected-file checks are recorded separately in the local final verification.

Run `python scripts/check_bootstrap_tables.py` for inventory checks; add `--source-root <cached-pinned-source-root>` to verify the primary source files. Without that option the tool explicitly reports primary sources unverified.

## Next concrete work

Build a test-only typed layout and deny-callback prototype before any Runtime exposure. Check104/56 byte sizes, field offsets, metadata values and null holes on Windows x64. Each module-loading entry needs its own typed deny callback with output clearing and a stop latch; the void callback must return void. Compiler-loading and context callbacks also need bounded rejection contracts. Direct native calls should prove argument/output/lifetime behavior before a separately reviewed table exposure experiment.

Do not return invented buffers, forward a private context function to ordinary retain, or claim startup success from this inventory. Runtime enumeration, application execution, performance evidence and Intel release qualification remain open.
