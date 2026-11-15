# CuPy Windows bootstrap diagnostic

This recipe selects a real external consumer; **CuPy is currently blocked, not supported**. `cupy.bootstrap` in the application registry pins its provenance. Its feature list describes the observed bootstrap scope, not a complete CuPy dependency manifest.

## Reproduce locally

Use Windows x64, Python 3.14 x64, Rust/Cargo and the existing CT build prerequisites. All downloads, installed wheels, raw logs and captures stay in ignored `.cache/`. Do not redistribute these vendor artifacts from CT. No machine CUDA driver replacement or global Python installation is needed.

From the repository root, download the three exact binary wheels from official PyPI and create a private environment:

```powershell
python -m pip --isolated download --index-url https://pypi.org/simple --only-binary=:all: --dest .cache/r2-apps/cupy-packages cupy-cuda12x==14.2.0 cuda-pathfinder==1.8.4 numpy==2.5.4
python -m venv .cache/r2-apps/cupy-env
.cache/r2-apps/cupy-env/Scripts/python.exe -m pip --isolated install --no-index --no-deps --find-links .cache/r2-apps/cupy-packages cupy-cuda12x==14.2.0 cuda-pathfinder==1.8.4 numpy==2.5.4
python scripts/run_cupy_bootstrap.py --environment .cache/r2-apps/cupy-env --wheels .cache/r2-apps/cupy-packages
```

If a restricted host cannot use its temporary directory, set `TEMP`/`TMP` to a newly created ignored local directory for those preparation commands only. Restore them afterward. Package preparation needs network access; the actual capture is offline. The runner rejects different wheel hashes/installed payload bytes or the wrong host ABI. It builds a fresh Driver, uses child-local `nvcuda.dll`, and does not load CT Runtime. No NVIDIA toolkit extras are installed. The first-blocker diagnostic does not require them; a later JIT/library workload will.

The command prints a run identifier, not private absolute paths. To verify the saved observations and current input identity without re-executing CUDA:

```powershell
python scripts/run_cupy_bootstrap.py --recheck .cache/cupy-bootstrap-runs/<run-id>
```

Recheck is a local integrity/contract check; it is not a new execution or an authenticated attestation. Source changes invalidate captures. Captures contain local environment paths and must remain private.

## What is measured

The fixed workload creates64 FP32 values, performs affine transformation and ReLU, and copies to host. Explicit NumPy CPU execution must match all64 raw words of the independent formula `max(0,(3*i-92)/16)`. The original CuPy implementation is unchanged. The source release commit identifies reviewed upstream code; the wheel hash, not that commit alone, identifies the distributed binary.

Five fresh children run in order: NumPy CPU control, nominal CuPy device-count prefix, observed prefix, nominal full CuPy workload, observed full workload. Children use isolated Python with `site` startup disabled and explicitly add the validated package directory. `.pth` and `sitecustomize` do not run. Native observation affects only the current child's CuPy `.pyd` import slots, wraps selected bootstrap function addresses and restores the slots. Return codes and non-address output values come from CT. Pointer identity, thread timing and Win32 last-error transparency are not claimed for the diagnostic. Nominal children have no instrumentation.

A changed nominal prefix or missing/changed/restoration-failed observation stops the runner before the full workload. A successful prefix requires a new execution-safety review; this diagnostic never automatically advances a future CT provider into kernel execution. With the current failed prefix, the full workload verifies where the unchanged consumer stops. CPU output is not CUDA output, and an expected failure can pass the diagnostic while `application_supported` remains false.

## Reviewed dependencies and next contract

- CuPy14.2.0 build configuration [links cudart_static](https://github.com/cupy/cupy/blob/dc1552a32f5489bdf6a5a721dfd952a92d47d934/install/cupy_builder/_features.py#L453-L460). Direct PE imports of the distributed Runtime `.pyd` contain no external cudart dependency, and the controlled test does not provide `cudart64_12.dll`. This exercises embedded Runtime to CT Driver bootstrap, not CT's own Runtime ABI.
- [Runtime implementation](https://github.com/cupy/cupy/blob/dc1552a32f5489bdf6a5a721dfd952a92d47d934/cupy_backends/cuda/api/runtime.pyx) calls Runtime C functions. [Dynamic Runtime softlink](https://github.com/cupy/cupy/blob/dc1552a32f5489bdf6a5a721dfd952a92d47d934/cupy_backends/cuda/api/_runtime_softlink.pxi) additionally supports Runtime version lookup; do not infer all Runtime calls use that DLL.
- Later array execution may require device/context properties, allocation/pools, streams/transfers, NVRTC, generated PTX and possibly CUDA toolkit headers/libraries. CuPy's larger FFT/linear-algebra/sparse operations have further library requirements. These are latent static dependencies; the448 bootstrap trace rows include optional lookups and do not establish a mandatory API count for this64-value task.
- Tinygrad commit `60687fe5855c013502bbd252ce776d8a11345791` was also tested. Its [system module](https://github.com/tinygrad/tinygrad/blob/60687fe5855c013502bbd252ce776d8a11345791/tinygrad/runtime/support/system.py) imports Unix `fcntl` on this path. Corrected public Tensor API usage still fails before CUDA lookup on this Windows host. No upstream patch, emulated module or silent older-version substitution was used. An initial wrong harness keyword was a harness error, not a CT failure.

- Follow-up Driver-only check for the same tinygrad revision: [the CUDA backend](https://github.com/tinygrad/tinygrad/blob/60687fe5855c013502bbd252ce776d8a11345791/tinygrad/runtime/ops_cuda.py#L24-L30) places the launch options, size and payload in one allocation. Its separate [diagnostic hook](https://github.com/tinygrad/tinygrad/blob/60687fe5855c013502bbd252ce776d8a11345791/extra/hook_cuda.py#L123-L130) queries parameters until the first error. The CT native fixture combines those two call patterns: it observes four parameters and an out-of-range error, builds the packed launch buffer and checks 257 sums and 64 guard values in the dynamic consumer on Intel Arc B390. Reproduce with `pwsh -NoProfile -File scripts/run_m3_smoke.ps1`. This executes a CT fixture; neither the tinygrad backend nor the hook runs in this check.

The next implementation must establish a truthful compatibility-version policy and audit the embedded Runtime bootstrap's required vs optional lookups before changing `cuDriverGetVersion`. Raising a number to hide unsupported behavior is not a fix. The observed failed call is concrete evidence, but its removal alone has not been shown sufficient; no counterfactual success or complete CuPy support is claimed. Full R2 remains open until that shared feature bundle is specified.

The pinned wheel metadata declares CuPy `MIT`, cuda-pathfinder `Apache-2.0`, and NumPy `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`. Retain each wheel's license files and bundled-component notices locally; this recipe redistributes no third-party package bytes.
