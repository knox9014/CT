# Default-stream synchronization results (2026-10-26)

Implemented `cudaStreamSynchronize` for the null/default stream in Rust. The current bounded profile is Runtime28, with Driver39 unchanged. This working-checkout diagnostic does not establish general CUDA compatibility, independent streams or asynchronous execution.

## Behavior and decision

Null stream uses exactly the existing `cudaDeviceSynchronize` path: ensure the current context (create/select the default primary context if none exists), drain retired modules belonging to that context, then call Driver synchronization. Existing ordinary contexts are preserved. Raw Driver errors map once; drain errors already in Runtime domain are preserved. Success does not clear a prior thread-local error.

Every non-null stream, including sentinel handles1/2 and pointer-width values, returns801 before Driver loading, initialization or context operations. No stream handle is dereferenced. There are no created streams or per-thread default-stream semantics yet. The current backend completes operations synchronously; this API does not add work queues or overlap.

A generic blocking `cudaMemcpyAsync` alias was considered and deferred. CUDA12 documents different synchronization behavior by copy direction and memory type; honest asynchronous copy needs a separate host-lifetime/order design. [NVIDIA CUDA12 synchronization rules](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-runtime-api/api-sync-behavior.html).

## Verification

- Runtime Rust87 passed, including five new tests covering preflight, initialization/current/selection failures, context creation/preservation, context-drain-sync ordering, failure short-circuiting, error domains and TLS.
- Workspace Rust tests passed; three pre-existing ignored tests remain ignored. Workspace/Runtime clippy and formatting passed. Current profile, compatibility and coverage registries passed their static checks.
- Python184 passed after source was frozen. Two new observation tests reject wrong byte counts, errors, types, extra fields and incorrect context claims.
- Official CUDA12.0.76 headers and authenticated MSVC `/W4 /WX /utf-8` compile the actual exported-function consumer. PE export count is exactly28.
- Actual Intel GPU: a guarded1028-byte HtoD/DtoD/DtoH roundtrip passed with null-stream synchronization between phases; fresh null-stream synchronization created a default context; subsequent synchronization preserved primary and separately created ordinary contexts. Success preserved a preceding TLS801. Device synchronization also preserved the ordinary context.
- Missing Driver: repeated null-stream synchronization returned Runtime35. Non-null calls were verified before any Driver module was loaded.
- Synthetic provider: synchronization returns709 while all other core functions forward to CT. Both stream and device APIs returned709 and preserved the ordinary context. This injects a return code; it does not induce a hardware fault.
- Prior attribute native checks were rebuilt/run with Runtime28 and all five modes passed: real Driver, core15+attribute only, missing attribute, foreign forwarding, absent Driver.
- Four existing default/kernel/symbol/u64 native ABI consumers were rebuilt; their pure modes passed against the same new Runtime DLL. Current export-count/stdout gates now use28; historical results/worktrees were retained.
- Pinned upstream vectorAdd source remained unchanged; new Runtime28 capture and replay passed the original custom shared-cudart application, trace/no-op controls and independent raw-buffer Driver checks. This does not prove the upstream build system or precompiled distribution.
- Original matrixMul was rebuilt and statically inspected, never executed. Missing Runtime import names decreased from12 to11. PTX still stops at `.shared` line32 (four declarations, four barriers,48 FMA occurrences). matrixMul also creates a nondefault stream, which remains unsupported even after this new export; compute-capability helper queries remain unsupported too.
- Independent subagent source review reported no defects. Review was read-only, distinct from the executed tests. Eleven pre-existing user-owned files retained their hashes; publication scans covered modified/new project text. No files were uploaded.

The earlier reused Runtime test target hit Windows linker LNK1114 when overwriting an existing import library. Tests were rerun successfully in a fresh ignored target; no source workaround or deletion of historical artifacts was needed.

## Local evidence

All captures share source fingerprint `e376873a6805dbc7665b8152e1220d28b923a2e19068bc7b19b65d838c2c06b2` and remain under ignored `.cache/` paths. Raw logs and vendor binaries are not publication artifacts.

| Capture | Manifest | SHA-256 |
| --- | --- | --- |
| Stream ABI/controls | `.cache/runtime-attribute-runs/65f6b5ce3a304395b1749a0d4cab2894/stream-manifest.json` | `683b2d3ca92fed473d205340891973322bc484c9ff1f6c24ec8ec4c70bfbe9aa` |
| Attribute ABI/controls | `.cache/runtime-attribute-runs/65f6b5ce3a304395b1749a0d4cab2894/manifest.json` | `bbe3b8472baa21fcca1875e37e15d8c8fcd10f957720b601dda21cc76098f56a` |
| Upstream vectorAdd | `.cache/upstream-vectoradd-runs/cc67b66e8dcb4b9a967305a1dfcbbd3b/manifest.json` | `3699be2bcc4131556d07db0464ae44ffd756021cc6569eee35eec2bd99813e2a` |
| matrixMul inspection | `.cache/matrixmul-triage/8b3d59d70bb74f5590102f3f759922c8/manifest.json` | `06ebfcb5b04288cd32b345451bcaf1421b14091a022533ff622dbc9c48e0c90a` |

The native folder also contains `existing-abi.json`. Vector replay is `replay-cc060d784bf24567ada3ee41cc3143d5.json` in its capture directory. To reproduce the native checks with the authenticated local diagnostic producer cache, run `python scripts/run_default_stream_sync.py`. It first regenerates the attribute checks, then builds and executes stream checks. Old captures are historical once source changes.

## Remaining work

matrixMul still needs stream creation, five event APIs, host allocation/free, async memcpy, and profiler start/stop (11 missing import names). It also needs supported nondefault-stream behavior, shared memory, barriers, float arithmetic and a valid cross-vendor device-selection policy. Adding names without these semantics cannot make it runnable.

Next design should establish ownership and submission order for stream objects before async copies/events. Preserve error propagation and memory lifetimes; define host-memory behavior before exposing asynchronous copy. Avoid advertising copy/compute overlap until it is implemented and measured.

[Implementation plan](superpowers/plans/2026-10-26-default-stream-sync.md). [Previous attribute capture](RUNTIME-DEVICE-ATTRIBUTE-RESULTS.md) describes Runtime27; those historical evidence hashes were preserved.
