# Bounded Runtime development implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task; user delegated routine choices and requests continued execution.

**Goal:** Resume actual Runtime-prefix development with a storage guard and verified, small Drive archive units.
**Architecture:** Independent cache-budget helper gates the new R2r runner. Existing R2q parent and diagnostic provider stay unchanged; separate virtual observer/worker/checker adds four children. Existing private encrypted archive helper handles each completed evidence unit.
**Tech Stack:** Python unittest, Rust diagnostic provider, pinned CUDA Runtime 12.9.79, Google Drive connector, existing AES-GCM archive helper.
**Spec:** `docs/superpowers/specs/2026-11-02-bounded-runtime-development-design.md`.

## Global constraints / review focus

40 GiB cache ceiling, 30 GiB free floor, 2 GiB conservative peak reservation. No compression assumptions or automatic evidence deletion. Recovery keys remain notebook-only. Preserve production Rust, HEAD/index/protected11 and all earlier work. Use `.cache/r2r-work/progress.md` and private checkpoints; no root commit/staging or managed-worktree edits. Review limits at equality, links/inspection failure, environment leakage, unexpected attribute/order and insufficient actual strict post-controls.

## Task 1: Storage budget guard

Create `scripts/cache_budget.py`, `tests/test_cache_budget.py`. Interfaces: `assess(cache_bytes, free_bytes, peak_bytes, *, cache_limit=40*GiB, free_floor=30*GiB)` returns a numeric-only policy result or raises ValueError; `ensure_budget(root, peak_bytes)` inspects the local cache and disk then applies the policy. Read-only CLI defaults to report, `--reserve-gib 2` asserts headroom.

- [x] Write and run failing tests for limits/equality, invalid/bool sizes, insufficient disk, local traversal and no mutation on refusal.
- [x] Implement the helper; run its focused tests green.

## Task 2: Explicit virtual Runtime prefix

Create `runtime_virtual_metadata_observer.py`, `runtime_virtual_metadata_worker.py`, `runtime_virtual_metadata_check.py`, `run_runtime_virtual_metadata.py` under scripts, and `tests/test_runtime_virtual_metadata.py`.

- [x] RED: exact actual 75/76/15 order, software-target labels, wrong/boolean values, policy leakage, native counters and actual strict 75 control.
- [x] GREEN: reuse R2q actual name/total forwarding and state validation; virtual child environment sets only the reviewed target. Strict controls have no CT variables and perform real 75 calls.
- [x] Runner gates before parent capture with `ensure_budget(ROOT, 2*GiB)`; fresh parent20 + new4 =24. Audit binds parent/build/binary/observations, preserves direct metadata and baseline controls. Saved recheck does not allocate another capture.

## Task 3: Qualification, review and storage lifecycle

- [x] Run focused and full Python tests, independent pre-native review; fix concrete findings.
- [x] Guard headroom; freeze a private source candidate; clean CPU 11-case lane, fresh24-child native capture and saved audit.
- [x] Record bounded results; check source/artifact/privacy/protected11/HEAD/index. Remove only the new CPU build target after tests, retaining reports/source/.git.
- [x] Archive the complete new run plus immutable source checkpoint (no CPU targets, local keys or account state), upload into a new private dated Drive folder and verify downloaded bytes/full archive. Keep newest run local; reclaim only transient staging data.
- [x] Final independent whole-change review and verification; report actual CUDA boundary and storage outcome. No shipping/application support claim.

Outcome: R2R-VIRTUAL-METADATA-RESULTS.md and DEVELOPMENT-STORAGE-RESULTS-2026-11-02.md. Added a separately verified/restored R2q unit and reclaimed only its older native run after exact inventory/dependency/quarantine checks; newest R2r remains local. One private packaging retry convenience issue is deferred in the results/ledger.
