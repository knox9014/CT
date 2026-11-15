# Genuine nvcc relaxed-memory consumer implementation plan

> **For agentic workers:** Use superpowers:executing-plans for inline execution and a final independent review.

**Goal:** Connect the relaxed global operand support to an unchanged genuine nvcc EXE using CT Runtime and Driver on Arc.

**Design:** Compile CT-owned CUDA C++ with the authenticated local nvcc12 and diagnostic MSVC host environment, default device-runtime registration and shared cudart. Two no-argument kernels copy between named volatile u32/u64 globals: this isolates register widening/truncation from the separate weak-pointer alignment gap. Require the producer PTX to contain a u32 load into a declared b64 register and a u32 store from b64, without PTX/EXE patching or inline assembly. Python owns expected values/guards. Run positive fresh seeds and a forwarding launch-noop control. Keep source, tool, command, output and bundle hashes in ignored diagnostic evidence, rehash before/after execution, and reject malformed outputs.

**Scope:** Genuine compiler-generated CT fixture, not upstream app, static cudart, device-runtime function execution, supported-host qualification, clean acceptance, performance or AMD support. Existing accepted artifacts and user-owned files stay unchanged.

## Tasks

- [x] Write closed-schema numerical oracle tests and see missing implementation fail; implement oracle.
- [x] Compile `.cu` fixture and prove required operations occur naturally in nvcc PTX; fail if they do not.
- [x] Build fresh CT DLLs and noop provider; execute original EXE through isolated app-local bundles, compare complete guarded observations, and prove noop is rejected by positive oracle.
- [x] Bind producer/source/commands/artifacts/execution observations to a local diagnostic manifest, verify hashes, and test tampered data rejection. Include fresh-seed replay.
- [x] Run relevant Python, Rust, validator/profile/privacy gates; independent review, then document exact achieved scope.

## Files

`tests/fixtures/relaxed_nvcc_runtime.cu`: producer input/observation-only consumer. `tests/relaxed_nvcc_oracle.py`, `tests/test_relaxed_nvcc.py`: independent expectations, metadata and negative controls. `scripts/run_relaxed_nvcc.py`: diagnostic build/bundle/observe/audit runner. Result document retains hashes and explicit limitations; raw manifests/binaries stay under ignored `.cache`.

## Completion record

Completed 2026-10-26. See [genuine producer results](../../RELAXED-NVCC-RESULTS.md).
Ruling: named globals isolate the existing pointer-alignment restriction; this test does not claim to fix it. Guards cover host copy destinations only. Independent review required fresh replay and explicit GPU identity; both were added before final capture. Raw artifacts remain ignored.
