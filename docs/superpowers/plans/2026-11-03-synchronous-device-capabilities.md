# Synchronous device capabilities implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline, followed by a fresh independent review.

**Goal:** Report the CT execution profile's copy/compute overlap and asynchronous engine count truthfully through Driver and CT Runtime.

**Architecture:** Attributes 15 (GPU_OVERLAP) and 40 (ASYNC_ENGINE_COUNT) return successful zero after ordinary Driver initialization, pointer and device validation. CT currently serializes Driver access and creates synchronous Level Zero immediate command lists. These values describe CT's exposed execution profile, not Intel silicon capabilities. Runtime forwards these attributes without acquiring a context and preserves existing output/error rules.

**Tech Stack:** Rust, Python unittest, official CUDA-header C++ ABI consumer.

**Spec:** This bounded design is contained in this document; the user delegated implementation choices and routine design approval in the conversation.

## Global constraints

Preserve root HEAD/index and protected11; no root staging/commit/push or managed-worktree edits. Retain immutable R2r source/evidence: its attribute15 refusal is historical, not a current-source expectation. No NVIDIA architecture, application-success or asynchronous-execution claim. Keys remain notebook-only. Use a cache headroom check before build output, one shared nonincremental target and private encrypted Drive evidence.

## Review focus

- Zero is a supported result, distinct from error801; unknown attributes remain unsupported.
- Runtime must forward the actual device handle, preserve error output and avoid primary/context acquisition.
- Invalid pointer/device precedence and success-preserves-last-error must remain unchanged.
- ABI observations require exactly eleven typed values, including two zero scheduling values; nonzero/bool/truncated observations fail.
- Guard before creating native output; existing R2r source-bound replay remains historical and must not be presented as validating the new Driver.

### Task 1: Runtime forwarding and Driver capability reporting

- [x] Extend Runtime forwarding regression to attributes15/40; run RED on existing implementation.
- [x] Return zero for15/40 in Driver after initialization/device checks; add them to Runtime preflight.
- [x] Run focused Runtime tests GREEN; confirm unknown attributes and error precedence stay intact.

### Task 2: Native ABI and bounded build

- [x] Extend official-header ABI consumer and Python oracle to exactly11 values; add rejection tests and watch RED.
- [x] Add pre-build budget guard and one target shared by both Cargo builds to native attribute runner.
- [x] Freeze source; run CPU qualification and five real native ABI controls against frozen source.

### Task 3: Review, retention and evidence

- [x] Fresh independent review; resolve significant findings with regression tests.
- [x] Scan publication files, verify source/index/protected11, record actual results and unverified official Runtime bootstrap scope.
- [x] Encrypt the new source/evidence unit, upload and verify recovery before reclaiming reproducible temporary build output. Preserve existing recovery keys and latest evidence.
