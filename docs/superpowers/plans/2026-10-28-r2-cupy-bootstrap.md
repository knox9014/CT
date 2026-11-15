# R2 CuPy bootstrap triage implementation plan

> **For agentic workers:** Use superpowers:executing-plans task by task, then one independent read-only review.

**Goal:** Pin a useful Windows CUDA consumer and preserve its actual first CT blocker, without claiming application support.

**Architecture:** Run an unchanged CuPy 14.2.0 Windows wheel in a private environment. A nominal child runs the fixed workload. A separate diagnostic child observes only that child's CuPy native module import slots and forwards CUDA resolver/bootstrap calls to CT with unchanged return codes and output values. It restores import slots before exit. The diagnostic changes returned function addresses and is explicitly instrumentation, never the nominal compatibility run.

**Tech stack:** Python 3.14 x64, ctypes/Win32, official CuPy/NumPy/cuda-pathfinder wheels, existing Rust CT Driver.

**Spec:** R2 in `2026-10-27-intel-qualification-next.md`; the bounded contract below.

## Contract and decisions

- Select CuPy 14.2.0 (`dc1552a32f5489bdf6a5a721dfd952a92d47d934`) distributed Windows cp314 wheel. The wheel hash identifies executed bytes; the release commit identifies reviewed source, not a reproducible wheel build claim.
- Current tinygrad `60687fe5855c013502bbd252ce776d8a11345791` fails on this Windows host on `fcntl` import before CUDA. Preserve it as a platform rejection. Do not patch upstream, fake `fcntl`, or silently downgrade.
- Fixed workload: 64 FP32 values, `x = arange(64)/8 - 4`, `maximum(x*1.5 + .25, 0)`, copied back to host. Independent oracle: `max(0, (3*i-92)/16)`, exactly representable FP32. NumPy is an explicit CPU control, never a CUDA fallback.
- Native execution is allowed only in isolated child processes with a timeout. No system DLLs/driver installation or machine settings change. No arbitrary GPU submission after a changed bootstrap outcome: the worker first checks the known failing device-count prefix and stops if it unexpectedly succeeds. The full nominal workload is a distinct run with the current same provider; future providers require re-review.
- Observe `GetProcAddress`, both cuGetProcAddress ABIs, cuInit and cuDriverGetVersion. Forward original function results, including errors and output writes. Do not replace unrelated returned function pointers. Null resolver probes, optional missing lookups, and observed failed calls are different categories.
- Parse import slots from bounded on-disk PE64 headers, validate RVAs and slot/image limits before touching the loaded module. Only trusted pinned CuPy `.pyd` modules in the current child are eligible. Restore all changed slots even on error. Do not log pointer addresses or local paths publicly.
- Record provider/package/source hashes, nominal/instrumented outcomes, CPU raw FP32 words and oracle, before/after module hashes, trace and restoration. Capture and deterministic recheck stay ignored. Reports contain sanitized evidence only.
- This is a bootstrap first-blocker qualification. Lookup inventories include optional CUDA functionality and are not the workload's proven required APIs. R2's complete dependency/feature bundle remains open if causality beyond the observed bootstrap call is unresolved.
- Preserve protected11, root HEAD/index and existing user changes. No staging, commits, pushes or vendor redistribution. Existing accepted worktrees stay untouched. Work inline in the authorized root because its ongoing dirty changes are intentional.

## Tasks

- [x] Write failing tests for bounded PE import parsing, exact numerical oracle and blocker classification (including missing evidence, optional failures and corrupted output).
- [x] Implement `scripts/cupy_bootstrap_check.py` (pure contract/parser), `scripts/cupy_bootstrap_observer.py` (child-local Windows observation), and `scripts/cupy_bootstrap_worker.py` (CPU/prefix/workload).
- [x] Implement `scripts/run_cupy_bootstrap.py`: pinned wheels/environment verification, fresh Driver build, controlled children, capture and recheck. Verify all installed package files against the wheel payload (allow only installation metadata and generated scripts outside payload).
- [x] Run CPU control, nominal prefix, nominal full workload, observed prefix and observed full workload. Require nominal/instrumented same failure and the actual failed Driver call in both prefix and workload before claiming an observed bootstrap blocker. Fresh CT Driver is used; CT Runtime is deliberately absent because CuPy's reviewed build statically links cudart. Do not equate this with CT Runtime compatibility.
- [x] Pin the candidate in applications registry as `runtime_static` / `distributed_binary`; pinned is provenance, not support. Add reviewable source/dependency/next-step notes.
- [x] Independent review, focused/full Python checks, clean CPU validation, privacy/protected/index/HEAD checks and results report. Product Rust bytes unchanged: do not relabel historic GPU qualification as fresh application success.

## Review focus

Pointer/calling-convention mistakes; incomplete hook restoration; interpreting lookup absence as a causal failure; altered nominal workload or silent CPU fallback; package/provider drift; sanitized records that conceal validation limitations.

## Execution ledger

- Initial exploratory CuPy prefix: import succeeds; device count raises Runtime35.
- Diagnostic spike: CT resolver is reached; forwarding both recursive resolver ABIs reveals an actual `cuDriverGetVersion` call returning801 with output0. This observation motivates a reproducible check, not a version spoof or a complete causal proof for every optional lookup.
- Ruling: restrict this change to R2 bootstrap evidence. A faithful compatibility-version contract and the static Runtime's broader bootstrap dependencies must be designed before changing Rust API behavior.
- Final qualification: five isolated children, exact CPU64-word match, zero CUDA output words, same Runtime35 in nominal/observed prefix and workload, actual Driver version query801/output0, both observers restored. Separate local recheck passed. See `docs/R2-CUPY-BOOTSTRAP-RESULTS.md`.
- Independent review found Python startup injection exposure, late observation gating and a build/source fingerprint race. Fixed with isolated no-site startup, immediate gates and pre/post-build fingerprints. A follow-up caught the fifth-child gate; fixed and regression-tested. Final read-only review found no remaining actionable issue.
- Whole R2 remains open: the complete bootstrap dependency bundle and truthful version contract are not yet established. These checked tasks qualify this bounded diagnostic only.
