# M3c: official CUDA vectorAddDrv sample on Intel Arc

Validated 2026-10-19 on the existing Windows x64 / Intel Arc B390 environment. The official NVIDIA CUDA Samples v12.0 `vectorAddDrv` host ran through CT and returned `Result = PASS` for its default 50,000 elements.

**Adjustment:** the unchanged upstream host reads `vectorAdd_kernel64.fatbin`. This test supplies actual NVIDIA NVRTC-produced PTX text under that expected filename. It does not supply the sample's original binary fatbin. This is unchanged host/kernel source with an adjusted module build/packaging path, not original-fatbin or complete CUDA compatibility.

## Provenance and build

- Upstream: [NVIDIA CUDA Samples v12.0 vectorAddDrv](https://github.com/NVIDIA/cuda-samples/tree/v12.0/Samples/0_Introduction/vectorAddDrv), commit `2b689228b746248b7bb7d2778d5ea0701669f7d3`.
- The harness checks the exact Git revision and a clean tracked source/helper tree. Host `vectorAddDrv.cpp` SHA-256: `c6cbb6c7ff368bb3244cc9b5be5553238203006390ee04105ff6cb0ab029a25b`; kernel `vectorAdd_kernel.cu`: `eadede64b1eed221fca04b5d5012eb5d479f680a39aa7e74268b53c13b2c8872`.
- Host source and helpers are unchanged. MSVC compiles the C++ host against official CUDA headers with an ordinary `nvcuda.dll` import library generated from CT's existing ABI declarations. Neither host source nor executable contains a CT-specific loader. Native compiler optimization/build options differ from the upstream nvcc build recipe.
- Kernel source is unchanged and compiled through official NVIDIA NVRTC 12.0.76, `--gpu-architecture=compute_52 --std=c++11`. PTX is not edited. [NVRTC is NVIDIA's runtime CUDA C++ to PTX compiler](https://docs.nvidia.com/cuda/archive/12.0.0/nvrtc/index.html).
- Generated PTX SHA-256: `008525ca03e2c4bbeab02fc306ffefd37eaa45ca7bf2190d883cb5720b3cc03d`. Application/PTX byte identity is checked during process-local staging. Rebuilds can produce different executable hashes; preservation is checked within each build/run.
- Explicit `--device=0` chooses the available device without invoking the sample's NVIDIA-specific performance-ranking path. CT reports compute mode DEFAULT because it implements shared contexts, without inventing NVIDIA compute capability or multiprocessor counts.

## Observed failures and CT adjustments

The upstream host initially failed with NOT_SUPPORTED=801 while querying compute mode. After CT changes, the same built executable passed without recompilation. Its preserved SHA-256 in that fail-to-pass experiment was `a3bde451e36d8faa95ea36155cc0799855cee7024fa238f2c15935d5d0f66dff`.

Actual compiler output exposed additional parser requirements: PTX8.0/sm_52, signed integer arithmetic/comparison, unannotated 64-bit pointer parameters and unused module globals. CT now supports a narrowly documented extension for those constructs. Pointer inference requires single-definition parameter-load registers used only in explicit global-address conversions; ambiguous u64 scalar cases are rejected. Module-global declarations are validated, but references remain unsupported. See [PTX profile](compatibility/ptx-profile.md).

No kernel-name/hash replacement, PTX rewriting or CPU execution fallback was introduced. Signed multiplication uses sign extension; signed comparisons use signed operands. The independent edge tests use raw two's-complement values and do not use computed negative values as memory addresses.

## Verification

| Check | Observed result |
| --- | --- |
| Official host sample's CPU comparison | PASS, 50,000 values |
| Independent generated-PTX checks | 6 sizes: 1, 63, 64, 65, 257, 50000 |
| Independent signed edge checks | 8 cases: negative/high-bit comparisons, signed-wide multiplication, modular multiply-add and 64-bit addition |
| Independent total | 14 cases, 50,970 values and 896 guards passed |
| Rust workspace | 19 tests passed, including actual GPU and 3 new profile tests |
| Python loader/publication | 14 tests passed, including rejection of binary fatbin assets |

Independent buffers start with NaNs and include guard regions, so missing writes/nonfinite results cannot pass through the sample's `fabs` comparison behavior. Signed results are checked through 64-bit equality and selection into ordinary float outputs. Raw compiler/sample output stays local and ignored; only aggregate results are published.

## Reproduce

Requires Windows x64, Git, Python, Rust MSVC, MSVC C++ tools and Intel Level Zero. Vendor artifacts are local test dependencies, not installed globally or redistributed with CT.

```powershell
git clone --depth 1 --branch v12.0 --filter=blob:none --sparse https://github.com/NVIDIA/cuda-samples.git .cache/vendor/cuda-samples-12.0
git -C .cache/vendor/cuda-samples-12.0 sparse-checkout set Samples/0_Introduction/vectorAddDrv Common
python -m pip download --no-deps --dest .cache/reference nvidia-cuda-runtime-cu12==12.0.107 nvidia-cuda-nvrtc-cu12==12.0.76 nvidia-cuda-nvcc-cu12==12.0.76
$env:CARGO_INCREMENTAL = '0'
./scripts/run_m3c_smoke.ps1
```

The harness checks pinned wheel SHA-256 values before extracting/loading any NVIDIA code. Runtime package `f595d66142e9ba5d1157d73ef06488735d814415a462714426f3989344e675eb`; NVRTC package `e6a0649a8519f49847ea636b2043dfe65d6cb4c3104ed12b69eb14c1413e5c1a`; compiler-header package `135809154702a6302713391d3b78b9f6b4584157f539103dbd2b1d5e5922a225`. The last package supplies missing CRT headers, not an nvcc invocation. Its compiler binaries are not used. The NVRTC builtin dependency is explicitly loaded from the same verified local package directory.

Upstream source retains its original license locally. No NVIDIA source, headers, compiled PTX, runtime DLLs, executable or raw run log is committed. The repository contains CT changes and its own harness/tests only. System NVIDIA/Intel drivers, global PATH, registry and original source directories are unchanged.

## Limits

This is one adjusted official sample on one Intel device. Actual fatbin parsing, original CUDA toolkit/nvcc sample build parity, NVIDIA original/coexistence comparison, broad external application coverage, CUDA Runtime/cudart, GPU performance comparisons and AMD remain unsupported or unverified. Full M3/v0.1 clearance is not claimed. Next targets are genuine PTX-bearing fatbin containers and additional external workloads with explicit API/precision checks.
