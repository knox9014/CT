# Inactive primary state foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Separate device-primary handle ownership from retained active usage before implementing private CUDART slot2.

**Architecture:** Extend existing Rust PrimaryContexts with get_or_create_unretained, used internally by retain. A reserved handle has references0; active requires both a handle and references>0. Public retain retains its existing create/reuse behavior. No private export/API or Runtime callback is enabled.

**Tech Stack:** Existing Rust state machine and unit tests; clean private checkpoint CPU validation.

**Spec:** This document's bounded design below; R2J-HOOKS-DENY-EXPOSURE-RESULTS.md identifies the observed boundary.

## Design and evidence

Pinned ZLUDA08b19b28b7c334936846b3aeb61a43aef053e9a1 driver.rs cudart_interface_fn2 obtains the primary context without public retain. Its cudart_interface_fn2_creates_inactive_primary_ctx test requires active0 and identical handle on subsequent retain. This is reference-derived evidence, not NVIDIA ABI certification. NVIDIA public Primary Context Management documents activation on retain and no TLS push. Existing CT public retain uses context presence as active and therefore cannot stand in for that private getter.

Directly calling public retain would violate the observed inactive requirement. Rebuilding native handle identity and resource storage is larger than required now. Chosen scope: introduce and test the ownership distinction in the existing state machine; preserve public behavior. The internal factory may allocate a native context; references0 means API-inactive, not proof of zero native resources. Runtime wiring, invalid-pointer/API validation, cross-thread tests and true native inactive service remain follow-up work.

Ruling: reset of an internally reserved handle follows CT's existing retirement/generation policy, preserving references0 and preventing reuse of the retired identity. This policy is not a claim about private NVIDIA reset/identity semantics. Release with references0 returns201 and does not consume an unretained handle. Later retain increments references only after successful creation and preserves identity. Overflow must be detected before any factory call.

Review ruling: the helper is named get_or_create_unretained, not inactive: reset can preserve positive usage, so recreating its handle can restore active status without adding usage. Only a fresh zero-reference reservation is guaranteed inactive. That internal policy is explicitly tested; private post-reset behavior remains unverified and blocks slot2 wiring.

## Global Constraints

- Preserve all prior dirty root work; edit only primary_state.rs, new tests within it and this phase's docs. No staging/root commit/push/upload or managed-worktree edits.
- Preserve all11 protected files and root HEAD/index.
- No table/ABI/version/profile changes; R2j remains historical pinned evidence and is not rechecked against modified source.

## Review Focus

- Repeated inactive lookup must not increase references or allocate again.
- Retain after reservation must share identity and activate; release at references0 must not destroy it.
- Allocation failure and overflow must leave prior state unchanged.
- Reset/retirement and device isolation must preserve existing public semantics.
- No callback connection or application-support claim may be inferred from state tests.

## Task 1: State machine (red, green, review)

- [x] Add failing tests in crates/ct-cuda/src/primary_state.rs for the five focus conditions; run focused Rust tests and observe missing-method failure.
- [x] Implement get_or_create_unretained, reuse it in retain with prechecked reference count, reject zero-reference release, and separate active from presence.
- [x] Run focused tests, format and independent review; resolve findings.

## Task 2: Regression and record

- [x] Create privacy-scanned private source checkpoint and run full CPU lane required; inspect test counts and failures.
- [x] Verify only primary_state.rs changed among product files, protected11/HEAD/index remain unchanged, privacy scan and diff check pass.
- [x] Record proven state transitions, reference limitations and next actual Runtime service work. Mark plan complete only with fresh evidence.
