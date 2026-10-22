# nvcc Fatbin Decoding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** P09a2-A: decode observed genuine nvcc12 PTX containers without weakening existing nvFatbin validation.

**Architecture:** Extend the existing pure Rust decoder with a distinct record profile. Keep the existing public decoding functions and add explicit allocation-failure propagation. Genuine producer bytes stay local; public tests construct CT-owned records.

**Tech Stack:** Rust/std, Python unittest, authenticated nvcc12.0.76 producer, existing Driver tests.

**Spec:** [kernel design](../specs/2026-10-22-runtime-kernel-design.md), sections1/4/5/10; [probe](../../P09a2-PRODUCER-PROBE.md).

## Global Constraints

- Windows x64 preview; no framework, release, AMD or NVIDIA execution claim.
- Preserve existing nvFatbin flags0x45/0x2045 and their option/name restrictions.
- Limits:16MiB image,256KiB PTX,8 candidates,1MiB aggregate decoded,256 records, record header64..4096 aligned8.
- New profile is exactly record72, flags0x41/0x2041; unknown options/layouts fail.
- Public artifacts contain no vendor headers/binaries, raw logs, personal paths or credentials. Preserve all11 user files; do not stage root Cargo.toml or ct-fatbin/Cargo.toml.
- Main agent implements; independent subagent reviews. This plan is pending user review.

## Review Focus

1. New flags attached to an old options layout must not bypass validation: `nvcc_profile_cannot_hide_options` (Task1).
2. Mixed records must not reset aggregate budgets: `mixed_profiles_share_limits` (Task1).
3. Declared expansion must fail before allocation: `decoded_limit_precedes_reserve` (Task2).
4. An allocation error must not become invalid PTX or panic: `allocation_maps_to_out_of_memory` (Task2).
5. A producer script's success must not substitute for byte comparison: `test_replay_rejects_changed_payload` (Task3).

## Files and contracts

- Modify `crates/ct-fatbin/src/lib.rs`; test `crates/ct-fatbin/tests/decoding.rs`.
- Modify `crates/ct-cuda/src/images.rs` for the additional exhaustive error arm.
- Create `tests/fixtures/p09a2/vector.cu`, `scripts/prepare_nvcc_probe.py`, `tests/test_nvcc_probe.py`, `docs/compatibility/nvcc-producer.md`.
- Modify `docs/compatibility/fatbin-profile.md`, `docs/compatibility/toolchain-lock-v1.json`, `scripts/check_toolchain_files.py` only for authenticated producer preparation/replay.
- Existing `image_size(&[u8])->Result<usize,Error>`, `extract_candidates(&[u8])->Result<Vec<PtxCandidate<'_>>,Error>` and `extract_ptx(&[u8])->Result<Cow<'_,[u8]>,Error>` remain intact; add `Error::Allocation`. Driver maps it to2, Runtime later maps it to2.

### Task1: Distinct nvcc record validation

**Interfaces:** Existing decoder entry points above; internal `enum RecordProfile { NvFatbin, Nvcc12 }` selected from header size and flags, before producer-specific metadata checks.

- [ ] Add failing CT-owned record tests to `decoding.rs`: `nvcc_plain_and_compressed_match` asserts identical PTX8.0/sm52; `nvcc_profile_cannot_hide_options` rejects nonzero bytes64..72, nonzero name fields, metadata!=64 and larger headers with new flags. `mixed_profiles_share_limits` accepts two valid profiles but rejects ninth candidate and decoded total>1MiB across both. Reuse existing malformed-record builders for truncation, overflow, bad padding, wrong decompressed length, missing NUL and old-option mutations.
- [ ] Run `cargo test -p ct-fatbin`; expect new valid nvcc tests to fail before implementation.
- [ ] Implement exact observed nvcc12 profile: kind1/version0x0101, header72, metadata64, name offset/length0, reserved44..56 and64..72 zero, PTX8.0/sm52. Keep old profile's own accepted PTX pairs. Plain compressed/decoded lengths0; compressed length>0, trailing zero padding<8, exact declared expansion. Shared PTX NUL/trailing-zero and all container limits remain enforced. Unknown flags/profile fields return Unsupported; malformed extents/data return Invalid.
- [ ] Run `cargo test -p ct-fatbin` and `cargo test -p ct-cuda images`; expect new and prior tests pass, including old nvFatbin strictness.
- [ ] Review diff and commit only decoder/test/profile-document paths: `feat: decode bounded nvcc12 PTX records`.

### Task2: Fallible decoder allocation

**Interfaces:** `Error::Allocation`; private `reserve_bytes(out:&mut Vec<u8>, additional:usize)->Result<(),Error>` and corresponding candidate reservation; callers retain existing return types.

- [ ] Add decoder unit tests with a test-only reservation fault hook: `decoded_limit_precedes_reserve` asserts over-limit data returns Unsupported with zero reservations; injected reserve failure returns Allocation. Hook is thread-local and absent from release builds. Separately test a pure Driver `fatbin_error(error:ct_fatbin::Error)->i32` mapper in `images.rs`: `allocation_maps_to_out_of_memory` asserts Allocation→2 without native load. Do not require dependency cfg(test) hooks to be visible in ct-cuda tests.
- [ ] Run `cargo test -p ct-fatbin` and `cargo test -p ct-cuda images`; expect absent fault hook/mapping tests to fail.
- [ ] Replace decompressor capacity and candidate growth with checked `try_reserve_exact`; reserve before extending. Add Driver exhaustive mapping, never treat Allocation as Invalid. Document remaining allocator-abort paths outside this change; no universal host-OOM claim.
- [ ] Repeat the two commands, then `cargo clippy --workspace --all-targets -- -D warnings`; expect all pass.
- [ ] Commit explicit decoder, Driver-image and test paths: `fix: propagate decoder allocation failures`.

### Task3: Authentic producer preparation and independent replay

**Interfaces:** `prepare_nvcc_probe.py prepare --output DIR --host-profile diagnostic|qualified`; `replay --manifest FILE`. Python `audit_probe(path:Path)->list[str]` validates manifest, rehashes source/compiler/header closure/artifacts, independently decodes raw LZ4 in Python and compares plain/compressed PTX. This replay does not claim Runtime execution.

- [ ] Add `test_nvcc_probe.py` cases `test_replay_rejects_changed_payload`, `test_replay_requires_header_closure`, `test_diagnostic_is_never_qualified`: tamper each artifact, omit an actually used header, or relabel unsupported host; each yields nonempty audit errors. Test fixtures are temporary CT-owned bytes.
- [ ] Run `python -m unittest discover -s tests -p test_nvcc_probe.py`; expect failure before helper exists.
- [ ] Implement prepare/replay and CT-owned `vector.cu` (17 unsigned elements, bounds guard,2x16 launch). Pin official component hashes and original Microsoft STL commit from the probe; authenticate every used transitive header, compiler/linker tool and library, recording member hashes and exact command argv. No header edits. Tool role IDs use dots, with explicit fixed member-path mapping in the preparation script; keep existing lock schema closed.
- [ ] Record compiler-qualified status separately: diagnostic requires explicit unsupported flag and pinned STL selection; qualified requires a CUDA12-supported compiler and no override. Missing qualified toolchain remains unavailable, never inferred from diagnostic execution. Include both `--no-compress` and compressed generation, `--cudart=shared --cudadevrt=none --generate-code arch=compute_52,code=compute_52`, plus actual producer/header provenance. Reject checksum mismatch; do not download/execute an unverified replacement.
- [ ] Run the unittest command; then prepare diagnostic into ignored `.cache/p09a2-producer` and replay its manifest. Expect authenticated genuine containers to yield identical decoded PTX and pass Rust decoding; changed payload fails. Publish commands/results classification only, not local files. If supported host is absent, record qualified as unverified.
- [ ] Commit only named CT-owned source/scripts/docs/lock edits: `test: authenticate and replay nvcc container fixtures`.

## Acceptance and next dependency

Run `cargo fmt --check`, workspace tests/clippy, Python discovery, `python scripts/check_coverage.py`, and publication scans. Independently review the decoder patch and genuine artifact replay. Retain existing38 required gates at the subsequent clean combined acceptance; these tasks do not imply those gates have already run. No passing count is predicted.

P09a2-B consumes this decoder and authenticated recipe via [Runtime kernel plan](2026-10-22-runtime-kernel.md). No Runtime export or PE whitelist change occurs in A.
