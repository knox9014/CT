# R2 CuPy bootstrap results

**Bounded diagnostic passed; CuPy remains unsupported.** An unchanged distributed CuPy14.2.0 Windows wheel reaches CT Driver, but its64-element FP32 affine/ReLU task stops during input creation. No CUDA result or performance measurement was produced.

## Observed execution

| Child | Result |
|---|---|
| Explicit NumPy CPU control | All64 raw FP32 words match independent exact oracle |
| Nominal CuPy device-count prefix | CUDARuntimeError35 |
| Observed prefix | Same error35; CT `cuDriverGetVersion` actually called, returns801/output0 |
| Nominal full CuPy workload | Same error35 at input creation |
| Observed full workload | Same error35 and actual Driver query801/output0 |

Each observed child records448 trace rows: one native GetProcAddress lookup,446 versioned resolver requests and one actual wrapped call. The actual call is `cuDriverGetVersion`; `cuInit` was not observed executing. There are308 successful resolver calls with null results and96 returning unsupported801. Those include optional feature/version/stream lookups and are **not** a list of404 mandatory missing workload functions. Resolver status, pointer availability and actual function execution are separate evidence.

Both observers restored their import slots. Diagnostic returned function addresses are wrapped; return codes and non-address outputs come from CT. Nominal children have no hooks. This establishes a concrete failed bootstrap call in the actual workload; it does not prove that changing this call alone would make the Runtime initialize. No version spoof, upstream patch, silent CPU fallback, kernel substitution or CuPy downgrade was used.

The test uses a freshly built CT Driver with no external cudart DLL. CuPy's reviewed build links a static Runtime; this does not qualify CT Runtime compatibility. Installed bytes were checked directly against the three official pinned wheels before execution, before both workload modes and afterward:3419 payload files, aggregate SHA256 `7cd93cdbd3ed0fe5996fc0a82d3d01594335d5a48fe8bf737c0800b63386bcc6`. Generated installation metadata/scripts are outside that payload count. Python runs isolated with site startup disabled; only the validated package directory and CT diagnostic scripts are explicitly added.

## Pinned evidence and verification

- Source fingerprint: `6a6c7c96a733417d46c61aeb30ca4c7149506ad5fc4525b1c15cf2f2f9623c8d`.
- Private source checkpoint: commit `c14c849859361c7dda705d97fb787685152bbb10`, tree `66b9d411e439cfc7de1d6d8f32fc52bd2622927b`. This is an ignored independent snapshot, not a commit in the user's root checkout. Ordinary result/plan reporting edits followed this checkpoint; the product fingerprint is unchanged.
- Fresh Driver SHA256: `702e319168413a1f77cd9c63b37831153ead83bcd72a6e8fc026b7c73ef53b94`.
- Local capture id: `1914658c97ae44b4bfefe9dbafae3db6`; capture SHA256 `10d4ba3caa2fd23df4342459a175d1d49d27dc85a569a75ff89c15d1a85267e4`.
- Separate deterministic local recheck SHA256: `1790875b4dd75401dc616b8c4d0882de8b0e6d3812362b93d3870cc7f504abc6`. This revalidates saved observations/current inputs; it is not a second CUDA execution or authenticated attestation.
- Focused11 tests passed, including malformed PE layouts, exact-word corruption, missing call evidence, altered observation/workload stopping later children, package drift/extra code and source edits during build. Important failures were observed before their fixes.
- Clean private source checkpoint CPU11/11 passed, including Python273, Rust207 with4 existing ignored tests, Runtime129, formatting, Clippy, registries and publication checks. No release claim.
- One independent read-only review plus follow-ups: startup/import control, immediate execution gates and source/build provenance findings fixed; final review found no remaining actionable issue.

All104 existing product files under crates/include and root Cargo inputs match the earlier R1c checkpoint. This phase changes diagnostic tooling and provenance records. Earlier R1 GPU results are historical qualification, not newly relabelled CuPy success. The original root HEAD/index and protected11 files were preserved. Vendor packages, logs, installed environment, captures and private snapshots remain ignored; no staging, push or upload was performed.

Preparation and replay commands, upstream source links, package pins, licensing metadata and rejected tinygrad candidate are recorded in [the recipe](CUPY-BOOTSTRAP-RECIPE.md). The release commit describes reviewed upstream source; only pinned wheel hashes identify executed distribution bytes.

## Next work and limits

### Current Driver replay (2026-11-06)

Rebuilt CT from the current checkout and ran the unchanged pinned CuPy 14.2.0 wheel through all five children. The NumPy control matched all 64 words. CuPy still returned Runtime 35 at device enumeration and at workload input creation, with zero CUDA output words. Both observed traces contained 448 rows and restored the import slots.

Compared in order to the original capture, each trace changed exactly two resolver replies: `cuFuncGetParamInfo` (request 12040, flags 0) went from 801/no pointer to success with a pointer, and `cuDeviceTotalMem` (request 3020, flags 0) went from success/null to success with a pointer. The only observed wrapped execution remained `cuDriverGetVersion` returning 801/output 0. Neither newly resolved function was observed executing; the trace does not establish whether either is mandatory after initialization.

The later [R2v attribute-17 boundary](R2V-RUNTIME-TOPOLOGY-RESULTS.md) was reached by a separate official Runtime experiment with diagnostic intervention. It is not the first failure in the unmodified CuPy path. Use the replay command in the [recipe](CUPY-BOOTSTRAP-RECIPE.md) to check whether an independently justified Driver change moves the actual CuPy boundary.

This completes the R2 **bootstrap diagnostic substep**, not whole R2 or R1. Next, establish the exact static Runtime build/version and audit the requested bootstrap contracts against official Driver ABI/semantics. Separate mandatory initialization calls from optional capability lookups. Design a truthful bounded `cuDriverGetVersion` policy before implementing it; a resolver version ceiling is not a supported CUDA-driver version. Then change only the justified common feature bundle, test invalid arguments/output/error semantics, rerun this unchanged consumer and preserve the next blocker.

The concrete next checklist is [the R2b contract plan](superpowers/plans/2026-10-28-r2b-static-runtime-contract.md).

No CuPy GPU numerical success, framework-wide support, GPU performance, concurrency, second Intel PC, NVIDIA comparison or AMD qualification is claimed. The64-value task is an external array-library smoke workload, not yet the meaningful end-user application workload required for final Intel acceptance.
