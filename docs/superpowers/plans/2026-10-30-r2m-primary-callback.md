# Primary callback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Connect the typed private context callback to CT's global native Runtime and prove it with actual public CUDA lifecycle functions.

**Architecture:** Rust-visible unsafe extern-system cudart_primary_context delegates to R2l acquire_primary(retained=false). Reexport as Rust API without no_mangle; production CUDA DLL exports/resolver/header/version profiles remain unchanged. Clear output before invoke so lock failure cannot leave a stale handle. Isolated ignored native test invokes the exact typed pointer alongside global public CUDA functions in one provider.

**Tech Stack:** Rust, existing Intel Level Zero backend, fresh private checkpoint, CPU lane, explicit native test and dumpbin export audit.

**Spec:** This bounded design and R2L-NATIVE-PRIMARY-ADAPTER-RESULTS.md.

## Decisions and constraints

- User explicitly requests continuous autonomous execution and commentary reports; do not pause between these reversible local stages.
- Preserve protected11, root HEAD/index and all previous work; no staging/root commit/upload/install or managed-worktree edits.
- Private callback must use the same RUNTIME as public calls. A separately linked rlib provider has its own state versus a separately loaded CT DLL; future bridge must link all entry points into one provider.
- Actual official Runtime/table wiring remains a subsequent stage. This step proves callback ABI, global state, lifecycle and unchanged DLL inventory, not application support.
- Valid nonnull output storage remains the caller's responsibility. Null returns1; valid output is cleared before initialization/lock errors. Pending retained usage after reset rejects801 through R2l.

## Review Focus

- Fresh-process preinit3 and null1 must not depend on another test's global state.
- Fresh reservation active0; subsequent public retain same handle active1; lookup must not add retained usage.
- Existing ordinary current context must survive lookup/reset/release; final destroy restores empty current state.
- Reservation reset and post-reset positive usage denial must clean resources without second cleanup.
- Rust visibility must not silently add a production C export. Verify actual DLL exports against current declared inventory.

## Tasks

- [x] Add CPU typed-pointer/null test and ignored exact native global-lifecycle test; observe missing callback failure.
- [x] Implement callback/reexport, format and run related CPU tests; independent review before native execution.
- [x] Freeze source; run required clean CPU lane, single native testcase and production DLL export audit. Verify hashes/source and privacy/protected11/HEAD/index.
- [x] Record evidence and immediately proceed toward one-provider guarded Runtime bridge; no checkpoint permission question.
