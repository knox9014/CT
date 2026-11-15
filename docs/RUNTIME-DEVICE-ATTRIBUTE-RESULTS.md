# Runtime device attribute results (2026-10-26)

Added `cudaDeviceGetAttribute` to the Rust Runtime. Current bounded profile is Runtime27; Driver39 is unchanged. This is diagnostic evidence from the working checkout, not a clean release or general CUDA compatibility claim.

## Behavior

Runtime forwards attributes 1..7 (maximum block threads, block dimensions, grid dimensions) and20 (compute mode) to the existing Driver. It uses the device handle returned by `cuDeviceGet`, rather than assuming handles equal ordinals. The optional symbol is cached separately from mandatory bootstrap15 and kernel5, resolved through the owned/pinned Driver module. Missing or foreign-forwarded symbols return Runtime error35 without disabling existing core APIs.

Preflight order is null output1, negative ordinal101, unsupported attribute801; these paths do not load Driver. Other nonnegative ordinals are validated by Driver. Output stays unchanged on every error. Initialization/device/query Driver errors map once; optional preparation35 bypasses that mapping. Success preserves prior thread-local errors. Querying attributes neither creates nor changes an execution context.

Compute capability75/76 and all other attributes remain unsupported801. CT does not invent an NVIDIA architecture for Intel. This combined-error precedence is CT's explicit bounded policy, not a general claim of NVIDIA parity.

## Verification

- Runtime Rust:82 passed, including five new tests for preflight, device handles, error domains/output preservation, TLS and independent cached resolution. Workspace tests also passed (three pre-existing ignored tests remain ignored).
- Python:182 passed. Full run was performed after freezing source; an earlier run overlapped edits and correctly rejected a changed source fingerprint.
- Workspace and Runtime formatting/clippy passed; Runtime profile, compatibility and coverage registry checks passed. Static registry checks are not execution evidence.
- Official CUDA12.0.76 headers compiled with authenticated MSVC, `/W4 /WX /utf-8`. Actual Runtime DLL has exactly27 exports. Function calls use official Runtime/Driver function-pointer types and enum ABI assertions.
- Five native modes passed: actual CT Driver; core15+attribute-only provider without module/launch exports; missing optional attribute; foreign-forwarded attribute; absent Driver. The foreign case proves the export resolves to the foreign module and Runtime rejects it. Missing/forwarded failures are repeated and subsequent device count still succeeds.
- Actual Intel device values matched direct Driver queries for all eight attributes. Returned values were `[1024,1024,1024,1024,2147483647,2147483647,2147483647,0]`; current context remained null. CPU spies provide the stronger evidence that Runtime makes no context calls. These limits are not a performance benchmark.
- Existing default/kernel/symbol/u64 native ABI consumers were recompiled and all four pure modes passed against the new Runtime DLL. Active exact-count/stdout gates now use27; historical artifacts and accepted worktrees were preserved.
- Pinned upstream `vectorAdd` source was unchanged. New Runtime27 capture and replay passed original application, trace/no-op controls and independent raw-buffer Driver checks. This remains a custom shared-cudart build, not an upstream build-system or distributed-binary claim.
- Original `matrixMul` was rebuilt and inspected without executing it. Static missing Runtime imports decreased from13 to12. Offline PTX still stops at `.shared` line32, with four shared declarations, four barriers and48 fused multiply-add occurrences. Device-selection helper compute capability queries remain an additional semantic blocker even after this export addition.
- Independent subagent source review found no blockers; review itself did not execute tests. Eleven pre-existing user-owned files retained their original hashes. Modified/new project artifacts passed publication scans; raw logs, vendor files and native evidence remain ignored/local. Nothing was published by this step.

## Local evidence

All captures share source fingerprint `058d3e6238c3151e4ee6a3af46ca1d4b9da1b711885c9256429d06197e8cfed6`.

| Capture | Local manifest | SHA-256 |
| --- | --- | --- |
| Attribute ABI/loader | `.cache/runtime-attribute-runs/862e800f3e86416490cc6efebcba61b0/manifest.json` | `d89d75738fc98a2a7302149a388589bb3c82c6946ef5d9f40c45fbb33aac6df1` |
| Upstream vectorAdd | `.cache/upstream-vectoradd-runs/4fac32b243b6448580e83b319d9c3fe4/manifest.json` | `661da1bd1fa7d4df3a501c23e7cf8bf0a495acd9f4dabf737fab996578dd8a9a` |
| matrixMul triage | `.cache/matrixmul-triage/7a68faa8cc3d4e7ba4f79982d7419830/manifest.json` | `c90f69c0dfb95d34a2a9c3a510392157269e9d4c44d6617e2cfb806e2f46baa5` |

Native capture additionally contains `existing-abi.json` for the four existing pure consumers. Vector replay is `replay-686a7f3374324c64b5ce28e5941cc3d9.json` in its capture directory. Local evidence is intentionally excluded from publication; hashes identify it without exposing raw host paths.

Reproduce with `python scripts/run_runtime_attribute.py`, `python scripts/run_upstream_vectoradd.py`, its `--replay` option, and `python scripts/triage_matrixmul.py` after selecting a fresh Runtime27 reference capture. These commands require the previously authenticated local diagnostic producer cache. Modifying source invalidates old evidence; update the reference pointer only after a successful fresh capture.

## Next work

Remaining matrixMul imports are five event APIs, two stream APIs, pinned host allocation/free, async memcpy and profiler start/stop. They require honest ordering, ownership and timing behavior. Shared memory, barriers and floating-point arithmetic remain separate translator/backend work. A cross-vendor device-selection/capability policy also needs design before CUDA SM-dependent sample helpers can select Intel correctly. Filling import names alone cannot make matrixMul runnable.

Implementation plan: [Runtime attribute plan](superpowers/plans/2026-10-26-runtime-device-attribute.md). Earlier triage: [matrixMul results](MATRIXMUL-TRIAGE-RESULTS.md); the13-import count there describes the historical Runtime26 capture.
