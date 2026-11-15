# Capacity-aware Fatbin Selection Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans and a final independent read-only review.

**Goal:** Select the highest-ranked validated PTX candidate that fits the owning device's bounded static-shared capacity.

**Architecture:** Pass native shared capacity into the pure image compiler/selector. Preserve translation, profile/metadata, duplicate, global identity and complete entry ABI checks for every candidate before using its fit result. Filter selection only by all-entry static-shared budgets; rank fitting candidates by the existing OLD7.0/sm50 then NEW8.0/sm52 order. Keep the final pre-native capacity gate. Read the owning context's device capacity before selection; never retry ordinary native compiler failures.

**Tech Stack:** Rust and existing nvcc/Intel diagnostic Python pipeline; no new dependencies.

**Spec:** This document; extends DEVICE-CAPABILITY-POLICY and DEVICE-SHARED-CAPACITY-RESULTS.

## Constraints and review focus

- Desktop checkout only; protected11 files unchanged; ignored local evidence; no staging or upload.
- All-unfitting nonempty validated candidates return801. Empty/mixed-raw inputs retain1. Bad metadata retains218. Invalid or unsupported candidates never disappear behind fallback.
- Every entry must fit individually, including aligned budgets; independent entry budgets are not summed.
- Rank and selection are independent of record order. If both fit, preserve previous preference.
- Raw PTX and one-candidate fatbins use the same device capacity; zero-shared code fits native0.
- Native errors are preserved without fallback. Device selection does not imply semantic equivalence between trusted kernel bodies.
- Compute-capability75/76, dynamic shared memory and export counts remain unchanged.
- Unit tests emulate smaller capacities; the physical Intel device currently reports CT's full16KiB bound. Do not claim physical constrained-device fallback execution without such hardware evidence.

## Tasks

- [x] Add failing selection tests: low capacity fallback both record orders, exact/padded/zero capacities, all-entry fit, no-fit, same-rank policy, malformed/unsupported/ABI/global conflicts despite nonfit. Observed missing capacity parameter then three behavior failures against old selection.
- [x] Pass native capacity through module loading; filter only final candidate selection, keep all validation and final native gate.
- [x] Update current policy contracts; run focused/full tests, clippy and independent review before freezing source. Rust204/4 existing ignored, Runtime129, Python219 pass; review no blockers and added malformed218 case.
- [x] Capture/replay fresh existing native/validator/upstream diagnostics; record what is synthetic versus native and privacy/protected-file results. All pass; default matrixMul still rejects75, injected positives and negative controls retain their expected outcomes.

Ruling: The user delegated implementation decisions and authorized continuation. This closes capacity-aware selection only; it does not establish production matrixMul device-query compatibility or a virtual NVIDIA architecture.

Final evidence: [selection results](../../CAPACITY-AWARE-FATBIN-RESULTS.md). Independent review found no blocker; added a missing-closing-brace218 control. Lower-capacity fallback remains a real-selector test with synthetic capacities, not a physical low-capacity GPU claim. Next virtual-target contract direction is proposed separately and not implemented.
