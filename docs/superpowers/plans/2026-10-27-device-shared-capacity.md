# Device Shared Capacity Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans; independent read-only review after implementation.

**Goal:** Expose a truthful bounded shared-memory capacity through Driver/Runtime attribute8 and reject modules exceeding the device capacity before native compilation.

**Architecture:** Preserve native Level Zero maxSharedLocalMemory as device metadata. The CUDA-facing static shared limit is min(native capacity, CT's16384-byte static shared profile). Compiled entry metadata retains the conservative aligned per-entry shared requirement. Validate every selected entry against the owning context device before native module creation; do not sum mutually exclusive entries. Dynamic launch shared bytes remain unsupported.

**Tech Stack:** Rust, existing Level Zero ABI, official-header C++ ABI consumer, Python evidence pipeline.

**Spec:** Design in this document. Follows MATRIX-RUNTIME-ISOLATION-RESULTS and prior static-shared profile.

## Constraints and review focus

- Preserve protected11 files, Desktop checkout only, ignored local evidence, no publication.
- Attributes75/76 remain801. No fake NVIDIA SM/clock metadata and no production matrixMul compatibility claim.
- Attribute8 is the bounded static capacity, not native total memory or dynamic-shared support.
- Null/ordinal/preflight precedence and output/TLS/context contracts stay unchanged.
- Native zero/small/huge limits must not wrap or overstate; zero-shared kernels may execute at zero capacity.
- All entry requirements checked; aligned objects and exact limit included; native compilation not reached on excess.
- Fresh official-header ABI and existing regression/validator/application diagnostic evidence required.

## Tasks

- [x] Write failing Rust tests for clamped capacity, per-entry aligned budget and multi-entry rejection; Runtime attr8 forwarding and attr9 preflight. Observed missing capacity metadata/helper and Runtime801; Python9-value checker also failed before implementation.
- [x] Store native capacity, centralize PTX static limit, retain compiled entry budgets, add pure pre-native capacity validation and Driver/Runtime attr8.
- [x] Extend official-header ABI tests/result checker and error controls to9 returned values; update bounded contracts. Real Intel full/minimal providers return16384 for8, with unchanged context and missing/forwarded/absent controls35.
- [x] Run focused/full tests and independent review; freeze fresh native evidence including injected matrix sample capture/replay. Record limitations and privacy checks.

Ruling: The user delegated implementation choices. Competitor source confirms virtual CC exists elsewhere, but does not establish a valid virtual CC contract for CT. Implement verified capacity plumbing first. This slice does not remove the matrix sample's architecture-selection blocker.

Independent review: no integration blocker. Added native-error-preservation regression and documented that highest-ranked fatbin selection precedes capacity validation; lower-candidate fallback is not yet implemented. Full Python tests detected a renamed test's stale profile reference; fixed it and repeated all219 tests successfully. Rust199 pass/4 existing ignored, Runtime129 pass, clippy/format pass. Frozen parent/application capture and fresh-process replay pass. See [results](../../DEVICE-SHARED-CAPACITY-RESULTS.md).
