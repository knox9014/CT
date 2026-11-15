# R0 Inventory and Source Candidate Plan

> **For agentic workers:** Use superpowers:executing-plans; one independent read-only review before frozen validation.

**Goal:** Reconcile bounded implementation declarations, register actual sample artifact references, scan real working-tree bytes, and preserve a reproducible private source candidate without touching the root index.

**Architecture:** Keep existing schemas and evidence tiers. Broad Runtime/streams declarations become explicitly bounded/partial; Driver streams get a distinct missing declaration. New vectorAdd/matrixMul registry entries pin immutable historical artifact/capture/replay hashes, not mutable latest pointers. Current fresh runs may produce different timestamp-bearing EXEs and are separate observations. A new working-tree scanner enumerates tracked+untracked nonignored files, rejects symlinks/junctions/escapes, reads actual bytes and keeps index/history modes unchanged. Source snapshots use reviewed bytes only, with an isolated private Git tree/commit and manifest; root files/index/history are unchanged.

**Tech Stack:** Existing Python validators/Git plumbing and JSON contracts, Rust/native regression pipeline unchanged.

**Spec:** R0 of intel-qualification-next.md; whole-project review2026-10-27.

## Constraints

- Preserve protected11 files, user changes and prior5a513 source evidence. No root stage/commit/reset/push and no SDK/private cache copying.
- Runtime/streams partial is not full CUDA support; static inventory is not execution success.
- Historical artifact hashes retain their original source fingerprint and scope. Fresh artifacts cannot silently replace those references.
- Source snapshot and original must have identical current bytes/product fingerprint. Private candidate commit is a local generated checkpoint, not published HEAD/CI evidence.
- Scanner errors never print sensitive matched bytes. Missing tracked files have no current bytes; symlink/broken link/junction/nonregular paths fail closed.

## Tasks

- [x] Failing tests: modified/untracked leak detection, ignored/force-added privacy paths, escape/symlink rejection; implement --working-tree and explicit report scope.
- [x] Failing metadata consistency tests; update broad Runtime/stream scope, Driver stream exclusion and virtual target feature; pin actual vectorAdd/matrixMul baseline records and scope documentation.
- [x] Test source candidate byte equality/root-index preservation/unsafe-path rejection; implement private snapshot manifest and isolated raw Git tree. Do not bundle local binary/vendor evidence.
- [x] Independent review, full CPU/profile checks, fresh native/validator/application capture/replay; validate captured source candidate and privacy/protected-file invariants.

Ruling: Metadata changes do not change GPU semantics, but current whole-source fingerprint changes. Preserve old evidence unchanged and produce fresh records rather than relabelling it. Snapshot metadata binds the fixed source tree; subsequent build logs stay ignored.

Acceptance: completed2026-10-28; see [R0 results](../../R0-INVENTORY-SOURCE-RESULTS.md). The first isolated CPU attempt exposed two cache-dependent configuration tests; synthetic fixture fixes, clean11/11 CPU and fresh98e40 Intel capture/replay passed. The tested checkpoint predates final report-only documentation edits; its product fingerprint is unchanged.
