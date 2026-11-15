# Native primary adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Connect R2k ownership distinction to CT's real native context factory and cleanup, without exposing private Runtime callbacks yet.

**Architecture:** Extract a common internal acquire_primary(Runtime, output, ordinal, retained) from public retain. False requests unretained ownership. Public retain preserves its prior backend-first preconditions. Nonretained calls reject pending positive usage after reset801 before allocating; that private lifetime contract is unknown. Use opt-in ignored native test with a local Runtime, real Backend and TLS restoration guard.

**Tech Stack:** Existing Rust Driver/backend, unit tests, private clean checkpoint CPU lane and one explicit Arc native test.

**Spec:** Bounded design in this document, R2K-INACTIVE-PRIMARY-STATE-RESULTS.md and R2J-HOOKS-DENY-EXPOSURE-RESULTS.md.

## Design and constraints

User delegated implementation decisions. Chosen scope is internal adapter/native proof; table publication or official Runtime success requires a subsequent reviewed boundary. Directly substituting public retain would activate the context and violate the fresh inactive requirement established by the pinned reference test. No new exports, API/profile/version declarations or header changes. No root staging/commit/upload/install or managed-worktree changes; preserve protected11 and HEAD/index.

The internal adapter checks null output, clears valid output before initialization/device errors, then invokes existing transactional state factory and writes a handle only on success. The existing public retain wrapper still checks initialization first, preserving its previous output precedence. Nonretained lookup of an existing active handle does not add usage; fresh reservation is inactive. Reset with positive usage and no handle is rejected801 by this adapter before factory invocation; retained acquire keeps CT's prior recreation policy. This is a bounded CT policy, not proof of NVIDIA private reset semantics.

Native resources may exist for an API-inactive reservation. No TLS operation occurs in acquisition/reset/release. Test Runtime is local and never published to global RUNTIME. All test native contexts are cleaned via normal CT cleanup; CPU suite does not implicitly use hardware. The native case is explicitly run alone with ignored tests enabled.

## Review Focus

- Null/uninitialized outputs and invalid device must never publish a handle.
- Empty and nonempty calling-thread context stacks remain identical through acquire/release/reset.
- A fresh inactive reservation is owned, repeated lookup stable, later retain same handle, final release cleans ownership/native resources.
- Unretained release201 must not consume resources; reservation reset cleans exactly once; stale identity is retired.
- Unknown positive-usage post-reset lookup rejects801 without allocating or changing counters/maps; public retained acquisition can still recover.

## Task 1: Tests then adapter

- [x] Add CPU tests for state pending-usage predicate and output/precondition behavior plus explicit ignored native local-Runtime test; observe missing-helper build failure.
- [x] Implement pending-usage predicate and internal acquire_primary, delegate public retain with unchanged backend-first ordering. Format and run CPU primary tests.
- [x] Independent review; resolve blockers before hardware run.

## Task 2: Native and clean regression

- [x] Freeze source in privacy-scanned private checkpoint; run full required CPU lane.
- [x] Run explicit single native local-Runtime test on Intel using private checkpoint and fresh process; capture command/log and assert one test passed.
- [x] Verify source fingerprint and only intended product deltas, protected11/HEAD/index, privacy and diff checks. Record evidence/limits; no claim that Runtime slot2 is connected.
