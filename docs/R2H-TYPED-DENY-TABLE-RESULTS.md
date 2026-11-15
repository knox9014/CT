# R2h: typed deny-table prototype and cross-language validation

## Result

Implemented a standalone test-only Rust fixture with typed104-byte CUDART and56-byte hooks layouts. Its nine callbacks deny every operation, clear valid outputs and record distinct hit bits. A C++ executable called them through the actual Rust DLL tables: all47 direct checks passed. Three standalone Rust tests also passed, including concurrent calls with independently owned output storage.

This fixture is not linked into CT and was not exposed to CUDA Runtime. It exports only ctTableGet and ctTableState for the direct tests, with no CUDA entrypoint or reset export. Its fixture getter returning a table pointer is not a successful cuGetExportTable implementation. No module, context or GPU resource was created, no buffer was supplied and no application kernel was launched.

## Verified contracts

Both languages check sizes, alignment, metadata and null holes; C++ asserts every field offset. Public CUDA headers check primitive widths/error values while private signatures remain derived from the pinned R2g public reference. Those headers do not certify private ABI semantics.

The three module-loading variants use their distinct signatures and output positions. The context-output function also clears valid storage. These status functions return801 for valid outputs and1 for null outputs. The primary-context and noarg compiler callbacks return801 without forwarding. The opaque void function returns void. Both void hook getters independently clear each valid pointer/count output even when the other is null; counts remain0. No input image, fatbin or opaque pointer is dereferenced. Deliberate invalid input addresses were tested only on these unread inputs; writable outputs were owned storage or null.

Every callback sets its own bit in one atomic mask. The stop flag is derived from the same mask snapshot, so concurrent observations cannot combine unrelated mask/stop states. The final nine-bit mask was511. This latch records that a denied operation was attempted; it does not automatically terminate a process or provide a sandbox. A future Runtime exposure must add its own orchestration gates.

The C++ harness verifies an initially clear state, each callback's exact next mask, status/output behavior, null combinations, stable static table pointers, same-file DLL load and successful unload. It makes no use of cached table/function pointers after unloading. The Rust tests also exercise repeated concurrent calls and null fixture getters/state queries.

## Execution and review

The local runner verifies pinned public sources, authenticated Runtime SDK extraction for headers, exact fixture exports and reviewed import sets for the DLL, Rust test executable and C++ host. It checks source/tool/artifact identities before each child, uses a timeout, validates exact result keys/types and stops on failure. The official Runtime binary in the SDK package is not executed or exposed to the fixture.

Independent design/implementation review completed. Review corrected an unsupported runtime-loaded claim to the narrower runtime-exposed flag and identified a missing import gate on the Rust test executable; that gate and a rejection regression were added. The initial C++ build stopped at a Windows max-macro collision; NOMINMAX fixed it, and the final fresh capture compiled with warnings treated as errors and passed. Final review performed a saved-evidence consistency audit, not another native execution.

The clean private checkpoint passed the full CPU11/11 lane, including Python317, Rust209 with4 existing ignored tests and Runtime129, plus formatting, Clippy, registry/profile and publication checks. The fixture's three standalone Rust tests and47 C++ checks are separate from those totals. Production Rust/Cargo/include bytes remain unchanged.

## Evidence identity

- Source fingerprint: `7cc95aa1975da0506726b88aa088c6e552b629032dda08905312eaf056922c16`.
- Private checkpoint commit: `7e0baa8df618bff1130eaeba06d6c17f6f8e5e7e`; tree: `4b96ac4839814276cc19b169779dc80126c37e46`.
- Final capture ID: `e783e46267594a85a5aa7182dc21cfa2`.
- Capture SHA256: `9149bacfeed51c7325451995135acbd16cf708b02e9e05d927f1a8721f20ec38`.
- Saved recheck SHA256: `1513d829e9b2e20c98c1decfdd87d678ca54a087a806beca30c4f45d1fe3b210`.
- Test-only DLL SHA256: `1d019251ae8366c088be5abde2fce8778adfd3085d701c24b938db114a286ae2`.
- C++ host SHA256: `ac4a61edf6d6c0b0a2ebfb2d650e8a0438d67068f6edbeaac51813da95f4b5ff`.

Saved recheck establishes local evidence consistency, not external attestation or another native run. SDK/source cache, binaries, logs, environments and absolute local paths stay ignored. No root staging/commit, upload, installation or accepted-worktree edit was performed. Privacy, protected files and root HEAD/index are tracked in the local final verification.

## Reproduce and next boundary

Run `python scripts/run_typed_tables.py` with the existing pinned local SDK/source setup. Override `--archive` or `--source-root` explicitly if needed. Use `--recheck <local-capture-folder>` for saved consistency checks. Standalone files are outside the production Cargo workspace.

Next, separately review a narrowly bounded Runtime exposure experiment: retain exact typed private loading/compiler/context guards and their latches, compare unchanged controls, and stop at the next unsupported query or callback. Passing direct-call layout tests does not authorize a successful private-table service, invented buffers, a shipping Driver version or application compatibility. Runtime enumeration and useful application execution remain open.
