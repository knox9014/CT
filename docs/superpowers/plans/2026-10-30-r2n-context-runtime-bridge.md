# Context Runtime bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Observe official pinned Runtime calling the successful native primary callback in one provider, stopping immediately at the next public name query.

**Architecture:** Test-only Rust cdylib links the existing ct_cuda rlib and typed deny fixture. A new static CUDART table replaces only slot2 with the proven callback; old deny tables remain available for C++47 contract checks. All public calls/private callback share the linked provider's RUNTIME. A Python observer gates exact query order and returns801 at the first post-context cuDeviceGetName. Production DLL exports remain unchanged.

**Tech Stack:** Rust diagnostic fixture, existing pinned Runtime/SDK/C++47 host, Python isolated observer/worker/checker/runner and CPU tests.

**Spec:** Bounded design below and R2M-PRIMARY-CALLBACK-RESULTS.md.

## Frozen expected prefix and lifecycle

Use exact R2j early-query/version/init/CUDART/hooks sequence and actual Driver count1/device0, but successful private context instead of denied mask2. Bridge native counter must change0→1, result0/nonNull1, while all deny bits remain0. At next cuDeviceGetName(length256,ordinal0), return801 without forwarding and latch stop. Static Runtime15D8D checks name result and jumps16AAB, returning initialized3/count−1 before further attribute calls. No hooks getter or module/launch operation may execute. Unexpected subsequent wrapped calls, private denials, counter changes or error result fail the child; do not expand gates after execution.

Keep provider loaded through Runtime IAT restoration and unload, snapshot native/deny states before and after Runtime teardown, then reset the inactive reservation through that provider's public reset and check inactive/current-null state. This is provider lifetime until process exit, not provider-unload proof. Raw lookup and resolver behavior remain the original missing private export; only labelled diagnostic v2 lookup supplies table access. All tables/function targets must be within the authenticated provider image.

## Constraints and review focus

- No new production API/profile/header/version change or root staging/commit/upload/install/managed-worktree edits; protect11 and HEAD/index.
- New diagnostic exports exactly ctTableGet/ctTableState/ctPrimaryTableGet/ctPrimaryState in addition to current46 CUDA exports.
- Preserve source/interpreter/runtime/provider/compiler/rlib/dependency identity before each child. Recheck saved bytes and finite metadata.
- Native callback at most one actual forward; repeat/latched deny cannot allocate a second reservation.
- Name-boundary stop must remain separate from unexpected public module/launch guards. All further wrapped forwarding blocks and invalidates the child.
- Controls use same diagnostic provider before/after; unchanged production controls remain captured separately. No unsupported buffer, broader private semantics or application success inferred.

## Tasks

- [x] Write failing finite checker/layout/state tests, then implement checker, fixture, observer and worker.
- [x] Implement fresh builder/capture/recheck using original8 production controls, C++47 deny-contract child, direct bridge child, before/after bridge controls and two context prefixes. Independently review before native execution.
- [x] Freeze source, run fresh native pipeline and required clean CPU; inspect states/teardown/provider identity and saved recheck.
- [x] Record evidence/privacy/protected11/HEAD/index checks and continue from the next observed boundary.

Diagnostic ruling: first capture b4bb733002f1497fac35710cc44d24de stopped at sample12000/exit42 with unexpected_context_state before the name boundary, despite final native state1/0/1. Preserve the failed capture. Add state/loader-role instrumentation only; keep all passing gates and forwarding behavior unchanged until the intermediate state is explained. A failed experiment is not a passing Runtime connection result.

Root-cause ruling: diagnostic capture b9b021393a1947f6b0767ef9c1285379 confirmed foreign-module FlsGetValue lookup at native1/0/0 during callback execution; restored=true. The generic lookup gate ran before module discrimination. Fix route discrimination before the CUDA gate: foreign lookups preserve their original function; same-provider lookups retain all strict native-state gates. Add failing causal test then implement scoped_lookup; record foreign metadata separately, not as successful native-context evidence. Both failed captures remain failed and passing prefix/final-state requirements are unchanged.
