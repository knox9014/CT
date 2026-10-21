# P05b Primary Reset Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, with independent final review.

**Goal:** Reset primary resources while preserving retained usage and safe failure behavior.

**Architecture:** Separate optional active context generation from checked device
reference counts. Reuse context cleanup/quarantine and TLS validation; add one v2
export and one independent native consumer gate.

**Tech Stack:** Rust, Windows x64 C ABI, Level Zero, MSVC, Python.

**Spec:** [reset design](../specs/2026-10-21-primary-reset-design.md)

## Global constraints

Default flags only. Reset canonical floor11000/ceiling12000. No legacy alias.
Fresh handle generation is CT policy, NVIDIA-unverified. Preserve11 user files;
no vendor artifacts or raw logs published. Reuse the existing clean candidate worktree.

## Review focus

- Outstanding references remain releasable after repeated reset.
- A fresh retain cannot silently discard old usage or reactivate old handles.
- Failed reactivation and overflow cannot consume usage or create leaked resources.
- Cleanup failure remains quarantined and is never retried by reset/release.
- Reset from another thread must preserve both TLS stacks and ordinary resources.

### Task1: State and reset API

Files: `primary_state.rs`, `primary.rs`, export/resolver header and Rust tests,
official ABI probes, profile/coverage registries, API documentation.

Interface: `PrimaryContexts::reset(device) -> Option<usize>` deactivates without
decrementing usage; existing retain/release signatures remain unchanged.

- [x] Add failing state tests for reset/release, reactivation failure/overflow and device isolation.
- [x] Implement optional generation, reset API/helper and integrated failure injection tests.
- [x] Add official signature and resolver tests, retaining unavailable legacy names.
- [x] Run Rust tests/clippy, profile/registry and official ABI checks.

### Task2: Native reset consumer and final validation

Files: `tests/p05b_cuda_app.c`, native build/check scripts, validation runner/catalog,
results and progress documentation.

- [x] Build ordinary static/dynamic consumers; show previous DLL lacks Reset_v2.
- [x] Exercise two-thread reset, pre/post-reset kernels, stale state, outstanding
  releases and ordinary context isolation on Arc with unchanged consumer/PTX bytes.
- [x] Obtain independent review and fix material issues with regression tests.
- [ ] Validate clean full combined candidate, preserve reports/user hashes and run publication scans.
