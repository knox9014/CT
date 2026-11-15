# R2r: explicit software-target metadata and bounded storage

The pinned official CUDA Runtime 12.9.79 progressed through actual `cuDeviceGetAttribute(75)` and `(76)` under the existing explicit `ct-sm52-subset-v1` software-target policy, returning 5 and 2. It then stopped on the actual unsupported attribute 15: Driver 801/output 0 and Runtime 3/count -1. The pinned official CUDA header calls attribute 15 `CU_DEVICE_ATTRIBUTE_GPU_OVERLAP` (deprecated in favor of asynchronous-engine information). It is a capability boundary, not evidence of a broken GPU.

These major/minor numbers describe the existing opt-in software target; they are not NVIDIA hardware properties or general compute-capability conformance. Default strict behavior was preserved. Two additional fresh processes with all CT environment variables absent actually initialized the provider and queried attribute 75, obtaining 801/output 0, ordinary device count 1, inactive primary state and null current context. The production Driver version remains 801/output 0. No application or shipping version is authorized.

The fresh pipeline passed 24 children: R2q's complete 20-child strict/name/total/context chain, two explicit virtual samples (diagnostic versions 12000/12090), and two actual strict post-controls. Both virtual samples used the real Intel name and total-memory functions, matching their direct/public controls: Intel(R) Arc(TM) B390 GPU and 17578409984 reported bytes. This total is not free memory, dedicated VRAM or an allocation budget. The private deny-table C++ consumer retained 47 checks; context counters stayed 1/0/1, private deny zero, Runtime unload/restoration passed and reset left primary inactive/current null.

Exact order, ordinal, scalar types, policy, actual values, context lifetime and subsequent-call latch are checked. Independent pre-native review found that the inherited loader helper could skip Runtime identity when a copied DLL was missing. Two temporary-bundle tests reproduced the gap; the fix requires a real pinned Runtime file/hash for virtual samples and absent file/None identity for strict controls. The negative tests then passed.

The immutable clean CPU lane passed 11/11: Python 354 tests, Rust 223 passed with 7 ignored, Runtime 129 passed, formatting/Clippy, profiles, registry and publication. The 7 ignored Rust cases are not reported as GPU passes. The independent CPU target was shared across both workspaces, then its 511685779 bytes were removed after CPU report and source validation. No production Rust behavior/exports changed in this phase.

The new diagnostic runner performs a read-only storage guard before creating its parent run: cache + 2 GiB estimated peak must fit within 40 GiB, and projected disk free must remain at least 30 GiB. Boundary/equality/type and no-mutation-on-refusal tests pass. Existing manual commands and older runners are outside this new runner's enforcement scope. See DEVELOPMENT-STORAGE.md for retention/archive/retrieval rules.

Source fingerprint: `efd1956be57db50e68a10ec379d990d171f246e7247eac213d839d4be5744f2c`.
Private checkpoint commit: `8b4e6c048cac053d74b49ac4531512213495d529`.
Fresh accepted native capture: `8a5ba83a09b6470c92376f7dbde6ca88`.
The saved native audit passed after capture; it was not a second GPU run. Source, SDK, compiler/interpreter, provider/build and observations are hash-bound. Raw paths/logs/binaries remain ignored. Protected11, HEAD/index, earlier source work and externally managed worktrees are preserved.

Next define truthful CT scheduling capability reports for the actual attribute15 boundary and inspect the next real Runtime request. Do not fabricate NVIDIA multiprocessor/architecture data or replace unsupported results merely to claim bootstrap success. Useful CUDA application execution remains open.
