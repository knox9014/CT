# R2s: truthful synchronous scheduling capabilities

CT Driver and CT Runtime now support device attributes15 (GPU_OVERLAP) and40 (ASYNC_ENGINE_COUNT), returning successful integer zero for the current serialized synchronous execution profile. These describe capabilities exposed by CT; they are not measurements of Intel hardware engines. Driver initialization, output-pointer checks and device validation precede success. Unsupported attributes still fail801. Runtime forwards the actual Driver device handle, preserves output on errors, preserves previous TLS errors on success and does not acquire/change a CUDA context.

The implementation basis is the Driver's global submission mutex and the Intel backend's Level Zero immediate command-list queue mode1. See the [Level Zero synchronous queue definition](https://oneapi-src.github.io/level-zero-spec/level-zero/1.1.2/core/api.html) and [official CUDA attribute definitions](https://nvidia.github.io/cuda-python/cuda-bindings/12.6.1/module/driver.html). This does not add asynchronous GPU execution.

The official-header C++ consumer passed five real process modes: normal, minimal forwarding, missing optional binding, foreign forwarded binding and absent Driver. Positive modes require exactly eleven values: limits1..8, compute mode20, overlap15 and engine count40; the final three are actual zero integers. Sentinels, unchanged current context, success-preserves-last-error and loader35 controls pass. The Python oracle independently rejects nonzero/bool/truncated scheduling results.

Native run: `5ced255eec0f427ca75d1121be917d75`.
Native immutable candidate: `0d5b8ece08114876b30a59de3716a089`.
Native source fingerprint: `35da991170ebe305a906ff2fcc7f4fc428f39d986e39774cad30e903291c2f04`.

Final CPU immutable candidate: `e76911dccedf4b33873c777b91d24139`.
Final source fingerprint: `95bad991ce9bc36c97e0060d767c1bb82dfd1f83bf01b7e75b354617f3084144`.
Final clean CPU qualification passed11/11 lanes: Python356, workspace Rust223 passed/7 ignored, CT Runtime129 passed, formatting, Clippy, profiles, registry and publication checks. Ignored tests are not counted as GPU passes.

The native/final candidates differ exactly in `tests/test_runtime_virtual_metadata.py`: the existing storage-refusal test now supplies the historical-source precondition. All product, compiler, Runtime and native-consumer input bytes are identical. Native results remain attributed to their original immutable source, and both sources travel with the backup. An earlier preliminary native invocation was rejected for source drift while review changes were being applied; it is not accepted qualification evidence. The first full CPU run found the obsolete fixture; that failure is not reported as a pass.

Independent static review found an integration issue in the historical R2r runner: its observer requires attribute15 refusal, incompatible with the new supported zero. The current runner now fails before budget checks/build creation when used with incompatible source and points to the immutable R2r source for historical replay. The original frozen R2r observer/expectation stays intact. The issue and fixture correction have regression tests and follow-up review; no Critical/Important findings remained in the reviewed delta. Review did not independently execute GPU or archive operations.

Native attribute builds now check40GiB cache ceiling and30GiB free-space floor with1GiB estimated peak before creating a run directory. Driver and Runtime builds share one run-local nonincremental target. The latest binaries/evidence are retained; dedicated CPU outputs and rejected preliminary build outputs are reclaimable after qualification and backup verification. The policy does not manage all historical caches or install background sync.

This phase validates CT's own Runtime ABI and Driver reporting. The official NVIDIA Runtime bootstrap has not been rerun past the new attribute15 response, and CUDA application/shipping support is not established. Next inspect its next actual request using the new scheduling-capability path; do not invent architecture values or infer application success from attribute counts.

## Storage qualification

The private encrypted Drive unit contains3134 files: both immutable sources and private Git objects, final CPU reports, the complete native ABI run including its build target, this result at packaging time and verification metadata. Logical171413710 bytes compressed/encrypted to18523642 data bytes, with zero exclusions. All five transferred data/helper/guide files were verified owner-only, read back byte-for-byte by SHA256, then fully restored. Both restored source candidates and the restored five-mode native observations passed consistency verification. This recovery check does not execute another GPU workload.

After independent deletion-boundary review, exact authenticated inventories were rescanned before cleanup. Temporary download/restore/volume copies, the dedicated CPU target, the rejected preliminary run and the backed-up native build target removed4103 files/1109529542 bytes. Current native binaries/observations, both source candidates, existing Runtime evidence and notebook-only recovery keys remain. The surviving native saved audit passed again after target removal. The full native target is recoverable from the encrypted unit; local archive directories now contain metadata only.

Measured cache grew from40150569324 to40185246321 bytes across this phase, a net34676997 bytes (about35MB), while preserving the new qualified code and evidence. The cache remains about37.4GiB; historical tool/cache data has not all been removed. The guard passed, and no background sync service or global cache eviction was installed. New archives and recovery mapping are catalogued privately; keys are never uploaded.
