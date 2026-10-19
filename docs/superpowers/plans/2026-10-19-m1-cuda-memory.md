# M1 CUDA API and Memory Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, then an independent review. Track checkable steps below.

**Goal:** Export a narrow CUDA Driver C ABI from CT and demonstrate genuine Intel GPU memory round trips in an independent C host.

**Architecture:** Extract the verified Level Zero ABI/loader into a shared internal crate. A native Intel backend provides device/context/allocation/synchronous transfer primitives. CT's DLL owns process-wide state behind a mutex, thread-local CUDA current-context stacks, and per-context allocation ranges. No kernel/PTX execution is introduced in M1.

**Tech Stack:** Rust/MSVC, C x64 host, Level Zero synchronous immediate command lists and pinned host staging; no external Rust dependencies.

**Spec:** `docs/CT-DRIVER-DESIGN.md` M1. User authorized incremental implementation and explicitly required privacy protection.

## Global constraints

- Never publish personal paths, contacts, credentials, raw personal inputs or logs. Enable local commit/push guards and inspect staged/outgoing Git blobs.
- Use ct_cuda.dll by explicit path. Do not replace nvcuda.dll or claim general application loading.
- Real device allocation/copy only; no CPU device-memory fallback.
- Caller-supplied C pointers must reference valid appropriately sized memory; reject nulls but do not promise arbitrary pointer validation.
- No fake CUDA version or compute capability; cuDriverGetVersion returns NOT_SUPPORTED and writes 0.
- Serialize runtime operations; keep current CUDA context thread-local, never dereference opaque user handles.
- On uncertain device completion, poison and retain native resources until process exit rather than freeing live memory.

## Review focus

1. Range validation must reject interior overflow, cross-context pointers, freed bases and u64 wraparound.
2. A context created in one thread must not automatically become current in another.
3. No caller buffer or temporary staging can be freed while a driver might still reference it.
4. Failed cleanup must not be reported as success; do not dereference stale opaque handles.
5. Publication checks must examine staged blobs and deleted past content in outgoing history, without printing matched values.

## Task 1: Publication safeguards

- [x] Extend .gitignore for personal/local artifacts and generated packages.
- [x] Observe synthetic-path/key/contact tests fail, implement redacted inspection, pass tests.
- [x] Test staged secret with safe unstaged replacement; test secret deleted in later commit. Both must block publication.
- [x] Check existing author/committer metadata privately and enable repository-local pre-commit/pre-push hooks.

## Task 2: Shared FFI and allocation range contract

Files: `crates/ct-level-zero`, `crates/ct-core`, M0 imports.

- [x] Extract existing ABI/loader without changing native behavior; store library handle as usize so owned loader can move between serialized callers.
- [x] Test `AllocationRanges` with synthetic bases: valid interior copy, exact end, adjacent allocations, overflow, removal, invalid base.
- [x] Implement checked insertion/range validation; rerun M0 and C/Rust ABI comparison.

## Task 3: CT DLL and native memory backend

Files: `crates/ct-backend-intel`, `crates/ct-cuda`.

- [x] Export initialization, device/name/limited attributes, context create/destroy/current/push/pop, allocation/free, HtoD/DtoH, synchronize, error lookup, explicitly unsupported version query.
- [x] Compile C host and observe missing/stub DLL functionality fail before backend implementation.
- [x] Add backend primitives using official Level Zero signatures and synchronous immediate list mode. Host pointers are staged in retained native allocations; driver return codes are mapped conservatively.
- [x] Implement monotonic opaque context tokens, TLS stacks, per-context ownership and checked memory ranges. Do not assume different contexts can use each other's pointers.

## Task 4: Integration, review and evidence

- [x] Independent C host: init failures, real device name, context isolation, round trips and interior offsets, invalid ranges/nulls/free-after-free/foreign contexts/stale handles, two host threads, repeated init/contexts.
- [x] Run Python publication tests, cargo workspace tests including M0 hardware test, C host, clippy, formatting and ABI oracle.
- [x] Independent review, fix material findings, rerun checks. Record M1 evidence and limits without private metadata.
- [x] Commit/push only after staged/revision/history guard succeeds, using a separate M1 branch based on M0. Do not merge main automatically.

## Ledger

- Existing public history: public GitHub account alias and noreply email only; local caches/results/build artifacts untracked.
- Publication tests: 5 passed, including staged-blob and deleted-history cases. Sandbox temp path visibility differed between Python and Git; test repositories now use validated workspace-local ignored .cache/privacy-tests.
- Ruling: M1 provides a deliberately narrow experimental Driver ABI, not complete CUDA conformance. Document unsupported queries instead of inventing capabilities.

- Task 2: range test failed against stubs, then passed after checked BTreeMap implementation. Shared FFI extraction preserved all16M0hardwarecases;12structure C/Rust ABI oracle passed.
- Task 3: independent C host first failed with missing DLL, then passed210checks after CT implementation. Native memory/context operations use Level Zero, not a CPU device-memory fallback.
- Review/fix: prepush annotated tags bypassed commit-only traversal; synthetic regression failed before branch-only metadata gate and passed after. Tags are now blocked pending explicit review.
- Review/fix: ze! lookup `?` escaped outer cleanup handlers; regression failed before closure confinement and passed after. Targeted reviewer marked both findings resolved.
- Privacy test infrastructure: temporary repositories use resolved workspace-local ignored paths. Preexisting sandbox temp visibility failure was environmental, not treated as a privacy-check pass.
- Verification: cargo tests including M0 real GPU, C host210checks, clippy-Dwarnings, formatting,12structure ABI oracle,6publication tests. Final staged and outbound-history scans are publication gates.
- Ruling: M1 is an experimental20export subset. Version/capability queries outside it fail explicitly. No PTX execution or broad CUDA conformance claimed.
- Publication: separate feature branch based on M0; no automatic main merge. Machine-local data/build outputs remain ignored.
