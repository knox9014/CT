# P05c Default Flags and Library Consumers Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline with independent whole-change review.

**Goal:** Connect default flag initialization/query and independently built library consumers to shared primary state.

**Architecture:** Add a pure flag classifier and two context APIs without changing
the native execution model. Build independent producer/consumer DLLs around shared
Driver handles and run them from an ordinary local host.

**Tech Stack:** Rust, Windows x64 C ABI, MSVC, Python, Level Zero.

**Spec:** [consumer design](../specs/2026-10-21-primary-consumers-design.md)

## Global constraints

Only flags0 supported. Known nonzero801, malformed1. Floors11000/7000, ceiling12000.
No legacy flag ABI or backend scheduling changes. Preserve11 user files and reuse
the managed clean candidate checkout. No raw/vendor/generated artifacts published.

## Review focus

- Zero flags while active must not consume usage or invalidate resources.
- Rejected flags cannot mutate current/active/resource state.
- Library unload is distinct from explicit usage release; no DllMain GPU calls.
- The second library must use resources after the first DLL unloads.
- Plugin bundling evidence must not imply automatic public-loader dependency support.

### Task1: Default-flags API

Files: `primary.rs`, `lib.rs`, resolver/header, official probes and registries.

- [x] Add failing flag classifier and resolver tests; implement syntax/support boundaries.
- [x] Implement SetFlags_v2 and GetFlags with current-context/error handling.
- [x] Match32 official ABI signatures and update bounded registries/docs.

### Task2: Independent library consumers

Files: producer/consumer/host C sources, shared test ABI, native build/check script,
validation runner and test catalog.

- [x] Build independent libraries and host; verify old DLL rejection and unchanged bytes.
- [x] Check flags and cross-library resource lifetime, producer unload, final release and fresh activation on Arc.
- [x] Obtain independent review and fix material findings with regression tests.
- [ ] Run clean full combined validation, publication scans and user-file preservation; preserve reports and publish a stacked draft.
