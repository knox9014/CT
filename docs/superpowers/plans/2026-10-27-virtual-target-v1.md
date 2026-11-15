# Experimental Virtual Target Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans and independent read-only review.

**Goal:** Execute the pinned original matrixMul product path with an explicitly enabled CT virtual target, without metadata-injection DLLs.

**Architecture:** Driver is the sole authority. First valid cuInit(0) attempt latches CT_VIRTUAL_TARGET before native initialization: unset/strict is strict; exact ct-sm52-subset-v1 enables virtual75/76=5/2; empty/unknown/non-Unicode is persistent init error1. Policy stays fixed even after native init failure. Nonzero cuInit flags do not consume the latch. Runtime never reads configuration: it delegates75/76 through its existing owned optional Driver attribute binding. No new exports.

**Tech Stack:** Rust OnceLock, existing owned Windows DLL bridge, official-header native C++ consumer, Python frozen capture/audit/replay and machine-readable JSON contract.

**Spec:** This design implements the independently reviewed virtual-target proposal. User explicitly authorized implementation.

## Constraints / review focus

- Desktop checkout only, protected11 files unchanged, .cache evidence only, no staging or uploads.
- Strict mode still rejects75/76 with real Driver801. Deliberate Runtime precedence change: these queries now load/init Driver; missing/foreign binding35, valid positive invalid ordinal101, invalid config1. Null1/negative101/other unsupported801 preflight stays Driver-free. Output/TLS/context behavior preserved.
- Physical Intel identity and real bounded capacities remain unchanged. Version queries remain0/801, SM/clock ranking unsupported.5.2 is a virtual selection target, not NVIDIA hardware/conformance.
- One process-fixed Driver latch, both API initialization orders, post-init env changes, invalid config persistence and invalid-flags-before-init tested.
- Existing parser/fatbin/ABI validation and late-registered unsupported code reject honestly; native errors never become successful fallback.
- Publish exact machine-readable supported pairs/API/operation/resource references and experimental/no-release scope.
- Actual original EXE nominal run uses CT Driver/Runtime directly. Observational Driver trace and no-launch/no-copy controls do not override metadata. Validate all finite outputs and replay; default rejection remains tested.

## Tasks

- [x] Write failing pure policy/latch tests and Runtime delegated CC tests. Implement Driver policy and Runtime preflight expansion, update affected default controls. Observed missing policy implementation and Runtime801 before forwarding change.
- [x] Create machine-readable contract and native official-header consumer: both API initialization orders, immutable env mutation, errors/guards/context/name/resources, missing/forwarded providers, late unsupported module rejection. All11 cases pass in capture/replay.
- [x] Add no-metadata-shim app capture/check/audit/replay with strict/invalid controls, nominal and traced positives, omission controls, pinned provenance. Test checker relabelling/mutation rejection. All8 app cases pass; normal bundles contain only original EXE and CT Driver/Runtime aliases.
- [x] Independent code review, full tests/clippy/format, fresh native regression and app evidence/replay; privacy/protected-file checks and results. Rust207/4 existing ignored, Runtime129, Python224 pass; review no blockers. CLI smoke also passes without a metadata shim.

Ruling: Driver delegation intentionally replaces previous Driver-free CC rejection. This gives one authority without additional CT discovery exports and is explicitly recorded/tested as a contract change.

Ruling on order coverage: the native consumer exercises both Driver-first and Runtime-first API initialization. Its Runtime DLL image loads first in both cases. Since policy is read only at cuInit and Runtime never snapshots configuration, initialization order is the tested contract; separate physical image-preload orders are not claimed. Record this distinction in results.

Evidence: [virtual target results](../../VIRTUAL-TARGET-RESULTS.md). Nominal app completion/PASS and traced independent numerical validation are distinct; the latter verifies7168 finite output words per pass and rejects both API-success NaN omission controls. Default query801 and invalid configuration1 remain separately captured. No release or general application conformance claim.
