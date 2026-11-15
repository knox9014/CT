# Native host allocation results (2026-10-26)

Added genuine Level Zero host storage through Driver cuMemHostAlloc/cuMemFreeHost and Runtime cudaHostAlloc/cudaFreeHost. Diagnostic contract: Driver41 / Runtime32. The nvcc cudaMallocHost wrapper also works through this path. Existing owned stream support remains synchronous; this change does not implement queued async copies or copy/compute overlap.

## Contract

Flags0 only. Unknown flag bits1; known unsupported combinations of1/2/4 return801. Null output/zero size1; Runtime creation preserves output on every error. Null host free1; exact base and owning current context required. Interior/foreign/double/cross-context free1.

Each Driver context owns up to128 host allocations/256MiB separately from device ranges. The Vec slot is reserved before native allocation; publication follows successful ownership commit. Free removes ownership only after native success. A failed native free retains storage and budget, poisons the context and pins the loader; no retry of uncertain frees. Cleanup unloads modules, destroys the command list, frees mixed device/host allocations, then destroys the native context; partial failure quarantines remaining state.

Runtime host symbols are a separate lazy complete pair resolved only from the already owned/pinned Driver. Missing or foreign-forwarded allocation or free symbols return Runtime35 without disabling core memory functions. Mandatory bootstrap15/kernel5 stay unchanged. Preparation35 is preserved; raw Driver errors map once.

No portable, mapped, write-combined, UVA or host pointer metadata expansion. Existing memory-type attribute2 remains801 and untracked address-range query returns500 with outputs unchanged. Queued async work still requires atomic acquire-use/free exclusion and lifetime retention; this synchronous map alone does not provide it.

## Verification

- Runtime Rust97 passed; workspace Rust tests passed with three pre-existing ignored tests. Workspace/Runtime clippy and formatting passed. Driver resolver tests include both verified version floors (host allocation2020/free2000); pinned cudaTypedefs.h supplies the official ABI.
- Python187 passed after final source freeze. Coverage/ABI fixture declarations were migrated for the new Driver functions; current static Runtime/profile/coverage checks pass without implying execution.
- Native CPU fault injection exercises actual Backend methods: writable native host storage, retryable OOM, fatal allocation poisoning, uncertain free retaining memory/no retry, mixed host/device cleanup and partial failure without double-free.
- Driver book tests cover reservation,128/256MiB limits, checked spans, exact-base freeing, duplicate/overflow rejection and flags. Malformed/alias native return values are validated at bookkeeping level; they were not injected through the complete public Driver allocation sink.
- Official CUDA header consumer calls actual Runtime exports. Positive native case allocated two host buffers and verified guarded1028-byte GPU roundtrip, rejection of interior/device-free/double/cross-context free and successful cleanup. Metadata restrictions stayed unchanged.
- Five negative loader modes passed: missing allocation, missing free, foreign-forwarded allocation, foreign-forwarded free, absent Driver. Repeated failures return35 with unchanged output. Available core device allocation/free still works. Forwarded cases prove the exported address resolves into the foreign module.
- Complete41 Driver function declarations from pinned official typedefs exactly match CT declarations. Independent static PE inspection of the tested DLLs confirmed Driver41 / Runtime32 names and functions; local pe-exports.json binds these counts to DLL hashes.
- Real nvcc host consumer uses cudaMallocHost with both flags0/1 owned streams, checks all32 kernel results and guard words, then frees host storage. Two fresh input runs passed; the complete host-extension no-op launch provider returned data-failure42 as required.
- Prior attribute five-mode, default-stream three-mode and owned-stream nvcc controls passed under the same new DLLs. Four existing default/kernel/symbol/u64 pure ABI consumers were rebuilt and passed.
- Original pinned upstream vectorAdd source remained unchanged; fresh custom shared-cudart capture and replay passed original application, trace/no-op and independent raw-buffer checks.
- Original matrixMul rebuilt and inspected only: missing Runtime names10 to8 (11 to8 across stream+host stages). It was never executed. Remaining names: cudaMemcpyAsync, cudaEventCreate/Destroy/Record/Synchronize/ElapsedTime, cudaProfilerStart/Stop. PTX still stops at .shared line32 (four declarations/four barriers/48 FMA occurrences), and CUDA compute-capability selection remains unsupported.
- Independent read-only review found no functional blockers. A stale comment in the native fixture describes a prior TLS error already cleared; the executed assertion correctly expects0, and later frees verify success preserves error1. This does not affect behavior.
- Eleven pre-existing user-owned files retained their hashes. Project-text publication scans passed; raw logs, vendor files, DLLs and captures stay ignored/local. Nothing uploaded.

## Local evidence

Source fingerprint: `a8ad0f539e6b8cdceae73199504f0842ec229deb99fc807f0c7cceec40846b48`.

| Capture | Manifest | SHA-256 |
| --- | --- | --- |
| Host/stream ABI and kernels | `.cache/runtime-attribute-runs/b05897d06d104380888fa8f4a0ca3ae0/host-manifest.json` | `ce1db9c5d4bca0b41f1daa65d9f2d4852c7697bcd5efd25d23dd3ba1cfed4560` |
| Upstream vectorAdd | `.cache/upstream-vectoradd-runs/0f7b44c45bb74928a004a6fd14d27405/manifest.json` | `873c7f4f99bfb89cf3912d3e8ec46883910e69803ddb5ddd64ac52923a9744f2` |
| MatrixMul offline | `.cache/matrixmul-triage/8c5a5fb3bd5241c09982b495f4e89231/manifest.json` | `8db844159bcb37fe0d01734118d4b0b168b7db7eb3d2371b3e35f9dbef2c8c98` |

Native folder also has owned-streams-manifest.json, stream-manifest.json, manifest.json (attribute), existing-abi.json and pe-exports.json. Vector replay: replay-4bdb4f3624894df89b97626de18d36b5.json. Reproduce with `python scripts/run_host_allocations.py` and the authenticated local diagnostic producer cache. Source changes make old captures historical; no clean-release or framework compatibility claim.

[Host implementation plan](superpowers/plans/2026-10-26-host-allocation.md). [Stream results](OWNED-STREAM-RESULTS.md) record the prior Runtime30/Driver39 stage. [Remaining dependency plan](superpowers/plans/2026-10-26-matrixmul-runtime-closure.md).
