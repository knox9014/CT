# M0 Intel Native Execution Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task by task. Steps use checkbox syntax.

**Goal:** Prove native SPIR-V vector addition on the user's Arc B390 without claiming CUDA compatibility.

**Architecture:** A dependency-free Rust x64 Windows executable dynamically loads the installed System32 Level Zero loader. A synthetic SPIR-V fixture is generated from a readable assembly reference. The executable copies inputs to device allocations, dispatches the kernel, copies results back, validates them, and releases resources.

**Tech Stack:** Rust stable/MSVC, Python standard library for fixture generation, installed Level Zero loader and Intel driver. No GPU driver installation or OS changes.

**Spec:** `docs/CT-DRIVER-DESIGN.md`, M0 only.

## Global Constraints

- Native backend experiment only; CUDA compatibility remains unimplemented.
- Use actual GPU execution; never CPU fallback.
- Use the current Windows environment and the verified B390; fail if no matching Intel GPU exists.
- Keep SDK references/cache and machine-local results out of public Git history.
- Never overwrite system GPU DLLs or alter system driver configuration.

## Review Focus

- Wrong/no-op device output must fail, including NaN and incorrect lengths.
- Nonmultiple dispatch sizes must be bounded and overflow-safe.
- FFI struct sizes, field offsets, and calling convention must match the pinned official C header.
- Copy/kernel ordering must be explicit and host buffers live through completion.
- Partial failures must release initialized resources; timed-out work must not free live buffers.

## Task 1: Oracle and dispatch validation

Files: `tools/ct-intel-smoke/{Cargo.toml,src/lib.rs,tests/validation.rs}`, root `Cargo.toml`.

- [x] Run `cargo test --workspace --test validation` against stubs and observe missing-behavior failures.
- [x] Implement `verify_sum(a: &[f32], b: &[f32], actual: &[f32]) -> Result<f32,String>` and `group_count(n:usize,group_size:u32) -> Result<u32,String>`.
- [x] Run all workspace tests; non-GPU tests must pass and the hardware test must remain explicitly ignored.

## Task 2: Readable and reproducible native fixture

Files: `tests/fixtures/vector_add.{spvasm,spv}`, `scripts/generate_smoke_spirv.py`.

- [x] Encode an OpenCL-kernel SPIR-V Physical64 module for bounded FP32 vector addition. CrossWorkgroup pointer arguments A/B/C, u32 length, GlobalInvocationId x.
- [x] Keep the source assembly beside the binary and record Khronos grammar version.
- [x] Generate fixture deterministically and verify byte stability. Run an official SPIR-V validator if available; otherwise disclose its absence and require real driver module compilation.

## Task 3: Native Level Zero execution

Files: `tools/ct-intel-smoke/src/{level_zero.rs,main.rs,lib.rs}`, `tests/gpu.rs`.

- [x] Run the explicit GPU test against the stub and observe failure.
- [x] Implement pinned-header-matched FFI, system-only loader, Intel GPU selection, properties, compute queue selection, context/list/queue, memory allocations, module/kernel, copies/barriers/launch/synchronization.
- [x] Produce a JSON report with GPU/vendor/device/driver properties, queue/group limits, tested lengths/group sizes, checked counts, and maximum error.
- [x] Exercise lengths 1,63,64,65,255,256,257,100003 with group sizes 64 and 128; lengths are positive and under u32 limits. Zero-length launch is rejected by the geometry helper.
- [x] Initialize output with NaN so missing writes cannot pass. Preserve a guard region after logical output and check it after execution.
- [x] Check release results on successful completion. On incomplete GPU work, retain live allocations until process teardown instead of freeing buffers still referenced by the device.
- [x] Compare Rust ABI layout against a tiny C program compiled with MSVC and the official pinned header.
- [x] Run workspace tests, explicit GPU test, CLI, formatting, and clippy.

## Task 4: Evidence and handoff

Files: environment matrix, decision record, M0 result documentation, README; machine-local reports under ignored `results/local/`.

- [x] Record toolchain, loader, selected GPU, API/driver versions, fixture hashes, commands and actual outcomes without user paths or hardware UUIDs in public output.
- [x] Review the completed M0 implementation, fix material problems, repeat relevant checks.
- [x] Commit the implementation on its feature branch and report exactly which M0 checks passed and which CUDA features remain absent.

## Execution ledger

- Start: native `zeInit(1)` returned SUCCESS and `zeDriverGet` reported one driver. Rust/MSVC and VS C++ tools exist.
- Ruling: execute the user-approved M0 scope in this session; the written plan concretizes that scope rather than requesting another authorization.
- Ruling: use a feature branch in the existing clean workspace; no second checkout or worktree is needed for this single-worker native probe.
- Pre-flight: fixture producer and runtime consume the same kernel name/argument layout; geometry helper must bound the fixture's u32 global index.

- Task 1: complete — observed 2 missing-behavior test failures, then 3 host validation tests passed.
- Task 2: complete — deterministic 584-byte SPIR-V fixture, hash 78c122989c637046319c5661a18aa0f2b9206407c63ea28ac261d1b6f6e64ca4; driver compiled it. Official spirv-val unavailable, not run.
- Task 3: complete — hardware test failed against stub, then 16 B390 cases passed. C/MSVC oracle matched all fields of 12 Rust structures. CLI JSON and cleanup verified.
- Review: corrected uninitialized typed host slices and borrowing across GPU writes; raw pointer initialization and post-completion immutable slices. Follow-up review confirmed P1 resolved. No deterministic host-side regression test can demonstrate this native FFI aliasing UB; source-level ownership correction plus actual GPU/suite rerun were used.
- Negative test: removed kernel output store; actual GPU run failed at numerical oracle with nonfinite value at index 0 (expected exit 1).
- Final checks: cargo fmt --all -- --check; cargo test --workspace -- --include-ignored; cargo clippy --workspace --all-targets -- -D warnings; CLI 16-case report and cleanup; git diff --check. All passed.
- Task 4: evidence and documentation complete. Publication remains a feature-branch draft; no merge to main is included.
