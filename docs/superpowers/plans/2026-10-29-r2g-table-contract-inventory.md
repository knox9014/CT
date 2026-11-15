# R2g public table-contract inventory

**Goal:** Turn pinned public declarations and local Runtime def-use evidence into a checked inventory before any successful private-table experiment. No native table-success execution in this phase.

**Evidence:** ZLUDA commit08b19b28b7c334936846b3aeb61a43aef053e9a1; pinned Runtime12.9.79; R2f actual query order. Public source is a third-party declaration, not an official NVIDIA ABI guarantee. Store source text only in ignored local cache; publish derived facts and links.

Independent read-only investigation confirmed CUDART_INTERFACE13 slots and TOOLS_RUNTIME_CALLBACK_HOOKS7 slots. The latter's slots2/6 are void getters, not CUDART slots2/6. Keep object/table def-use explicit. Buffer counts are elements, while table slot0 is bytes. Private module-loading entries1/6/8 require separate guards; slot7 is void and slot12 has no arguments. The context callback also has semantics beyond public retain.

- [x] Pin primary source identity and source-file hashes, correlate static call sites and preserve unknown semantics.
- [x] Add failing tests for metadata/function confusion, null holes, wrong return type/arity/convention, table identity, element/byte units and altered source evidence.
- [x] Implement an offline inventory and checker. Its outputs always deny native success authorization; it checks declarations/units and reports future obligations, not runtime compatibility.
- [x] Independently review the inventory/checker; run focused/full CPU validation and privacy/protected-file/index checks. Preserve production code and existing experimental captures.

Next candidate: separately review a minimal exposure experiment whose private code-loading entries all have exact typed deny callbacks and stop latches. Do not expose a successful table, return buffers or forward context operations before per-slot layout/lifetime/behavior checks and a new bounded design review.

## Outcome

Pinned two primary files; checked two tables/nine callable slots. Five focused tests and clean full CPU11/11 passed. Independent review verified pointer types, reported-count wording and static Runtime provenance. No native success-table experiment or production Driver change was performed. See `docs/R2G-TABLE-CONTRACT-RESULTS.md`.
