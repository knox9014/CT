# M3a CUDA Application Connection Implementation Plan

> Execute inline with superpowers:executing-plans, test-first implementation and final independent review.

**Goal:** Run byte-identical standalone Windows x64 CUDA Driver API consumers through a local CT DLL bundle.

**Architecture:** A dependency-free Python CLI inspects bounded PE import structures. It stages explicit application/PTX copies in a fresh ignored bundle, places CT as application-local nvcuda.dll, and launches the original application bytes using an argument array. Two ordinary C applications verify static and dynamic CUDA loading on Arc B390.

**Spec:** `docs/CUDA-CONNECTION.md`; existing `docs/CT-DRIVER-DESIGN.md`, M3. User authorized incremental development and explicitly reaffirmed CUDA connection.

## Constraints and review focus

- No system DLL, driver, registry, global PATH or original application modification.
- Only x64 PE executables; no recursive dependency copying or arbitrary import patching.
- Bounds-check PE header/RVA/import/thunk structures; reject malformed, delay and ordinal CUDA imports.
- Reject unsupported CUDA static symbols and cudart dependencies. Dynamic requirements remain unknown.
- Fresh bundle, no filename collisions; preserve executable/PTX bytes and report hashes.
- Child arguments preserve boundaries; retain exit status and do not expose local paths in CT errors.
- Synthetic fixtures only in Git; all bundles, logs and binaries ignored.

## Tasks

- [x] Write failing synthetic PE tests: static CUDA imports, unsupported symbols, truncation/RVA overflow, x86/DLL/delay/ordinal rejection and dynamic classification.
- [x] Implement PE inspection and CLI `inspect`, `run`; test explicit bundle staging, collisions, byte identity and argument/exit handling.
- [x] Build independent static-import and dynamic-load C consumers using a synthetic import library, external PTX and CPU output/guard checks. Observe ordinary loading failure without CT, then success through CT.
- [x] Regress M2/M1, Python privacy tests, Rust formatting/clippy; independent review and fixes.
- [ ] Record exact support/remaining NVIDIA and application compatibility gaps, scan publication, commit and create a stacked draft PR.

## Execution ledger

- Missing CLI module observed before implementation. Five initial loader tests then passed, followed by real GPU execution through both ordinary CUDA loading modes: 514 output values and 128 guards. Application/PTX bytes were preserved.
- Independent review found unchecked FirstThunk when OriginalFirstThunk existed, and unsanitized argparse errors. Both regression tests failed before fixes. All seven loader tests passed after correction; reviewer independently confirmed no remaining actionable findings.
- M2's 53 cases / 613,056 checks, M1's 210 checks, all 13 Python tests, Rust formatting and clippy passed.
- Ruling: use a fresh native smoke build directory each run — the local sandbox/native librarian denied overwrite of a previous import library despite writable attributes — costs extra ignored local build space. Fresh-directory build and full native CUDA connection test passed.
- No NVIDIA original execution/coexistence result, external-app compatibility or full M3/v0.1 claim. Exact gaps documented in M3a results.
