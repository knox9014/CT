# Device memory properties Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add truthful, optional Intel backend total-memory metadata needed by the next public CUDA bootstrap query.

**Architecture:** Minimal repr-C DeviceMemoryProperties and dynamically resolved zeDeviceGetMemoryProperties. Backend total_memory accepts exactly one nonzero property, with count/fill/recount observations all1; no array summing, guessed RAM ratio or free-budget substitution. Missing/ambiguous query returns unsupported without changing Backend::open. Public CUDA exports remain unchanged in this stage.

**Tech Stack:** Rust backend/fake foreign calls, official Level Zero v1.27.0 C header layout oracle and compile-only signature check, explicit Intel native test, clean CPU lane.

**Spec:** Design and source evidence below; next public wrapper is a separate integration step.

## Evidence and limits

[Level Zero API](https://oneapi-src.github.io/level-zero-spec/level-zero/1.18.31/core/api/apis/device.html#zedevicegetmemoryproperties) reports per-memory-type properties. [Intel's accounting guide](https://github.com/intel/compute-runtime/blob/master/programmers-guide/DEVICE_MEMORY_ACCOUNTING.md) distinguishes UMD-advertised totals from physical capacity and currently free/budgeted memory. Use the reported nonzero total unchanged. Multi-property aggregation is not established by current evidence, so reject it. Three counts establish observed count consistency only, not an atomic snapshot or fixed VRAM size. Independent read-only research checked the pinned local header: stype7; Windows x64 expected size296/align8/total offset32/name40; actual C comparison remains required.

Public CUDA later needs the v3020 size_t-pointer ABI; legacyv2000 uses unsigned-int output and must not receive an8-byte write. This stage does not expose either CUDA function or increase exports.

## Constraints and review focus

- Preserve protected11, HEAD/index and prior work; no root staging/commit/upload/install or managed-worktree edits.
- Check device index before optional symbol/native calls. Missing symbol unsupported, errors preserve native codes, total0 or counts other than1 unsupported.
- Every native error stage marks api.keep_loaded for device-lost/reset, with no Context available to poison. No automatic retries.
- Initialize stype7/nextnull and capacity1 before the fill call; no allocation proportional to a driver count.
- Native evidence binds actual selected device and driver-reported bytes, without allocating GPU-wide memory. Ordinary CPU tests skip hardware.

## Tasks

- [x] Write failing Rust ABI/backend tests and ignored native test, observe missing type/method failures.
- [x] Implement ABI type and optional backend query, extend fake FFI for count/fill/failure semantics; run targeted tests/format and independent review.
- [x] Extend C/Rust layout outputs and official-header compile-only signature check. Freeze source; run clean required CPU, ABI comparison and explicit native query with captured identities.
- [x] Verify privacy/protected11/HEAD/index/product delta, record limitations, then proceed to public CUDA wrapper/next guarded prefix.
