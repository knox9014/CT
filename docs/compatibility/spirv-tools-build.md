# Local SPIRV-Tools validator pin

This is a CT source build of the official validator, not a vendor-supplied
binary or a CUDA semantic-equivalence certificate. No Vulkan validation flags
are used for CT Kernel modules.

| Input | Revision / SHA-256 |
| --- | --- |
| [SPIRV-Tools v2025.4](https://github.com/KhronosGroup/SPIRV-Tools/tree/7f2d9ee926f98fc77a3ed1e1e0f113b8c9c49458) | `7f2d9ee926f98fc77a3ed1e1e0f113b8c9c49458` |
| Tools source zip | `713643963d2fab54a626a9054406d80e37c3d291b45b18ad43d5f033beeb0049` |
| SPIRV-Headers, required by the pinned Tools DEPS | `01e0577914a75a2569c846778c2f93aa8e6feddd` |
| Headers source zip | `b96204f9a68cf5aca4fcad17c60feb51176af52b9790609e7439fa589f87d5f2` |

Archives are from `https://codeload.github.com/KhronosGroup/PROJECT/zip/COMMIT`,
with PROJECT and COMMIT replaced by the corresponding values above. Extract
only under ignored `.cache/universal-foundation/vendor/`. Place the pinned
Headers tree at the Tools tree's `external/spirv-headers` directory.

Observed build tools: MSVC 14.51.36231, Visual Studio Community 2026,
CMake 4.3.1-msvc1, Python 3.13.9. CMake is bundled with the installed Visual
Studio; discover its installation with vswhere. Use its actual executable as
`$taskCmake`; no machine PATH edits are needed.

```powershell
$env:FORCED_BUILD_VERSION_DESCRIPTION = '7f2d9ee926f98fc77a3ed1e1e0f113b8c9c49458'
& $taskCmake -S $taskToolsSource -B .cache/universal-foundation/spirv-build `
  -G 'Visual Studio 18 2026' -A x64 -DSPIRV_SKIP_TESTS=ON `
  -DSPIRV_SKIP_EXECUTABLES=OFF -DSPIRV_BUILD_FUZZER=OFF `
  -DSPIRV_TOOLS_USE_MIMALLOC=OFF -DSPIRV_TOOLS_BUILD_STATIC=ON `
  -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded
& $taskCmake --build .cache/universal-foundation/spirv-build `
  --config Release --target spirv-val --parallel 1 -- /nodeReuse:false
```

Restore the previous process environment variable after building. The forced
version description prevents source archives nested inside CT from accidentally
reporting CT's Git revision. It changes metadata only, not validation rules.
The archive hashes are input pins; the resulting executable has its own hash
in `toolchain-lock-v1.json`. A different build must not silently replace that
executable pin. Bitwise reproducibility across toolchains/paths is not claimed.

Validation uses `--target-env opencl1.2` (SPIR-V 1.0, Kernel, Physical64).
The module enables Kernel's `ContractionOff`; Shader-only `NoContraction` is
invalid here. All Kernel integer types have Signedness 0; signed interpretation
comes from signed operation opcodes. Both rules are checked by the official
validator and CT regression tests.

## Hosted CI source builds

`scripts/prepare_spirv_tools.py` verifies both archive hashes before extracting
and building in a fresh ignored directory. It writes a **separate local execution
lock**, with the newly observed executable hash, under `results/local/`. Pass
that lock and its explicit local executable binding to the validator lane. This
does not change the repository's executable pin or the corpus expectations.
Source archive identity is fixed; a new build's binary identity is recorded as a
different execution identity. Cross-toolchain binary reproducibility is not claimed.

The hosted Windows CI runs CPU and real validator controls only. It never uses
the notebook's GPU runner, copies vendor binaries into Git, or treats absent
NVRTC/Arc/AMD/NVIDIA execution as a pass. The workflow's actual hosted execution
must be checked separately after publication; local validation is not CI evidence.
