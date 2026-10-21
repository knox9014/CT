# P05a Primary Context Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Let independent CUDA Driver consumers retain and share a device primary context.

**Architecture:** A small pure state machine owns checked retain counts and stale
identities. The runtime owns native contexts and serialized cleanup; TLS remains
thread local. Reuse the existing clean candidate worktree for final validation.

**Tech Stack:** Rust, Windows x64 C ABI, Intel Level Zero, Python, MSVC.

**Spec:** [primary context design](../specs/2026-10-21-primary-context-design.md)

## Global constraints

Default flags only; no legacy release/reset/flags promises; 12000 resolver ceiling.
Preserve original user files and publish no vendor artifacts or raw local reports.

## Review focus

- A failed first native creation must not publish a handle or reference.
- Final release from a different thread must not change either TLS stack.
- Releasing one consumer must preserve another consumer's native resources.
- Ordinary contexts must remain usable after primary release.
- Cleanup failure must quarantine rather than retry or resurrect stale resources.

### Task 1: Shared primary state and ABI

Files: `crates/ct-cuda/src/primary_state.rs`, `primary.rs`, `lib.rs`, `entrypoints.rs`,
`include/ct_cuda.h`, Rust resolver tests, official ABI probes, compatibility registries.

Interfaces: `PrimaryContexts::retain(device, create) -> Result<usize, i32>`,
`release(device) -> Result<Option<usize>, i32>`, `active`, `owns`, `retired`.
The runtime supplies native creation; a final release returns the context to retire.

- [x] Add failing pure-state and resolver tests; observe failure.
- [x] Implement checked sharing, tombstones, three exports and shared cleanup.
- [x] Match pinned official signatures/version floors; update static declarations.
- [x] Run Rust tests, clippy, static registry/profile checks and official ABI probes.

### Task 2: Independent consumer and full regression

Files: `tests/p05a_cuda_app.c`, `tests/p05a_primary_check.py`,
`scripts/run_p05a_smoke.ps1`, `scripts/run_validation.py`, compatibility docs/catalog.

- [x] Build two consumers and observe pre-feature DLL rejection.
- [x] Exercise two threads, shared native bytes/modules, nonfinal/final release,
  stale context/module/function handles, fresh activation and ordinary isolation.
- [x] Add the native case to Arc/combined lanes; keep hosted CPU free of GPU work.
- [x] Obtain independent whole-change review; fix material findings with regression tests.
- [ ] Validate a clean candidate with all required lanes, scan publication, preserve
  user hashes, and publish a stacked draft PR with actual evidence and remaining limits.
