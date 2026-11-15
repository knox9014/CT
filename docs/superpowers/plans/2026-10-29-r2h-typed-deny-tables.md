# R2h typed deny-table prototype

**Goal:** Verify Windows x64 layout and direct-call behavior for the R2g declarations before any Runtime table exposure. Test-only standalone Rust DLL, no Cargo/member/production/export changes.

**Design:** repr(C) typed104/56-byte tables, usize metadata and zero holes. Nine extern-system callbacks have distinct atomic hit bits; stop is derived from the one atomic mask. No reset export, forwarding, input-pointer reads, GPU/Runtime dependency or successful private operation. Module/context callbacks clear valid output and return801, or1 for null output, latching on every entry. Void hooks independently clear valid output/count storage and return void; count stays0 and no buffers are invented. Void slot7 returns void; noarg compiler slot returns801. Own fixture-only getters expose tables/state for direct tests; no CUDA export.

- [x] Write failing standalone Rust tests for sizes/offsets/holes, all deny callbacks and null combinations, stable storage and atomic latch behavior.
- [x] Implement `tests/bootstrap_tables.rs`; compile standalone Rust tests and a cdylib. Do not expose to CUDA Runtime.
- [x] Add `tests/bootstrap_tables_abi.hpp` and a C++ direct-call harness. Compile against authenticated official primitive types, while labelling private prototypes third-party-sourced. Verify exports/imports before native execution, then all9 distinct hit bits, output sentinels/null cases, repeated pointer stability and unload in an isolated child with timeout.
- [x] Add a reproducible local runner with source/tool/artifact/observation identities and saved recheck. Independent review before execution and final review of completed artifacts. Run focused/full CPU regression plus privacy/protected-file/HEAD/index checks.

Ruling: use the primary workspace and ignored private source/evidence checkpoints; preserve accepted worktrees, dirty changes and protected/root index. No staging, root commit, upload or installation.

Future Runtime exposure remains a separate reviewed experiment. Passing this test-only ABI fixture does not implement an actual private table service, authorize a numeric Driver version or establish application compatibility.

## Outcome

Final fresh capture passed standalone Rust3 and C++47 direct checks, nine distinct bits and verified unload. Exact dependency gates cover both native executables and the fixture. NOMINMAX resolves the initial compile-only header clash. Final independent saved-evidence review and clean full CPU11/11 passed. No Runtime exposure or production implementation change. See `docs/R2H-TYPED-DENY-TABLE-RESULTS.md`.
