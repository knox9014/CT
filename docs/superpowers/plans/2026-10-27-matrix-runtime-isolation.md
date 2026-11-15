# Matrix Runtime Isolation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for implementation and an independent read-only review at the end.

**Goal:** Execute the pinned original matrixMul EXE's complete Runtime path while explicitly isolating its unsupported NVIDIA architecture-selection gate.

**Architecture:** Keep production attributes75/76 unsupported. A test-only Runtime DLL forwards all exports to CT except those two queries, where it injects5.2 solely for the pinned sm52 sample. A separate observational Driver wrapper captures original inputs/output, poisons allocations and supplies API-success omission controls. No shim goes into product crates or installation.

**Tech Stack:** Rust CT, MSVC C, Python unittest, existing nvcc diagnostic producer.

**Spec:** This document's design and global constraints; follows the matrixmul-runtime-closure ledger and independent runtime_attribute_review advice.

## Global constraints

- Desktop checkout only; preserve protected11 files; no stage/commit/upload.
- Exact original source, PTX and EXE hashes; unchanged original source/EXE.
- All captures under ignored .cache; no system DLL replacement.
- Report metadata_injected=true and production_compatible=false, release_claim=false.
- CC5.2 is injected test metadata matching producer target, never Intel hardware or full CT feature coverage.
- Original PASS alone is insufficient; all output words must be finite and match an external binary32 oracle.

## Review focus

- NaN false PASS: poisoned no-launch and no-copy runs must fail the external checker.
- Forwarding: all40 Runtime exports exist; only75/76 intercepted, ordinary preflight delegated.
- Commands/identity: pin providers, executable, arguments, input/output files; source drift fails audit.
- Repetition: observe301 launches,2uploads,1download and3frees, not just one kernel.
- Scope: baseline normal CT must still reject architecture query; injected execution cannot be relabelled as production compatibility.

## Tasks

- [x] Write checker tests for finite outputs, wrong inputs/extents, omission signatures, closed trace and metadata scope. Observed missing-module failure; four tests pass.
- [x] Implement external checker, diagnostic Runtime shim and Driver capture wrapper. Compiled all variants with /W4 /WX; PE dump confirms39 forwarders and only the query local.
- [x] Implement capture/audit/replay using fresh original vectorAdd and matrix triage, actual SPIR-V validator before GPU, and strict provenance. Baseline fails801; two positive shapes and no-launch/no-copy controls execute unchanged EXE.
- [x] Run unit/native checks, fresh replay and independent review. Fixed parent artifact overwrite and confirmed fresh acceptance.
- [x] Record actual evidence and remaining production device-policy blocker; privacy/protected-file checks.

Ruling: The user delegated routine design choices and repeatedly authorized continuation. No new approval needed for local reversible diagnostic work. No full NVIDIA architecture compatibility is inferred from one sample.

Review correction: preserve the parent chain's ct_cudart.dll. The vector reference Runtime is copied as matrix-runtime-original.dll; bundle roles map it to ct_runtime.dll or baseline cudart64_12.dll. Independent review confirms all identities are consistent. A capture interrupted by source drift is not accepted evidence.

Verification: Python219 passed; Rust workspace195 passed/4 existing ignored and separate Runtime129 passed. Existing target linking failed with LNK1114/access5; fresh ignored target with incremental disabled passed. Protected11 files preserved; publication scan clean. Frozen capture and replay pass; full details in [results](../../MATRIX-RUNTIME-ISOLATION-RESULTS.md).
