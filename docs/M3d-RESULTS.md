# M3d: genuine CUDA fatbin execution on Intel Arc

Validated 2026-10-19 on Windows x64 / Intel Arc B390. The unchanged official NVIDIA vectorAddDrv host now runs with a **real binary fatbin created by NVIDIA nvFatbin**, rather than M3c's PTX text under a fatbin filename.

## Producer and preservation

The original kernel from pinned CUDA Samples v12.0 is compiled by NVRTC12.0.76 as in [M3c](M3c-RESULTS.md). Official nvFatbin12.4.99 packages that output with `-64 -cuda -host=windows -compress=false`. The resulting container is passed unchanged to CT through the original host's `cuModuleLoadData` call. No container writer, PTX substitution or decompression is used in CT's runtime.

The [official nvFatbin API](https://docs.nvidia.com/cuda/archive/12.4.1/nvfatbin/index.html) creates containers consumable by CUDA module loading, and supports disabling compression. This is a genuine NVIDIA-created artifact; it is not a reproduction of the original sample's complete nvcc build recipe or original multi-architecture fatbin.

| Artifact | SHA-256 / size |
| --- | --- |
| Compiler-input PTX | `008525ca03e2c4bbeab02fc306ffefd37eaa45ca7bf2190d883cb5720b3cc03d` |
| NVIDIA-created raw fatbin | `e75b900ffb9f738abdeb9936d5a6c981fd982afa3186050b59992f7230501493`,5232 bytes |
| Preserved executable in old/new CT experiment | `882ed5f1a29d56be31abc63f2c9be59a48b424c5eb20a84173c838bd15f94f38` |
| nvFatbin Windows wheel12.4.99 | `398b9ea66d888ae858e74935658dae5f9149fad0978b3ed55bb2d5113dec78fc` |

The same built executable failed with error218 on prior CT and passed after the decoder was connected. Source/helper files remained unchanged at upstream commit `2b689228b746248b7bb7d2778d5ea0701669f7d3`. Fresh rebuilds also passed; executable hashes may differ between builds. Staging checks byte identity within each build/run.

nvFatbin can normalize PTX comments/padding while packaging. The compiler-input hash is therefore separate from the container and extracted text; no byte-identity claim is made between pre-packaging and extracted PTX. CT preserves the produced container bytes and interprets the embedded PTX semantics.

## Observed checks

| Check | Result |
| --- | --- |
| Unchanged official host with binary fatbin | PASS,50,000 values; also passed through public `ct.py run` |
| Independent fatbin-derived GPU checks | 6 sizes:1,63,64,65,257,50000;50,450 values and384 guards passed |
| Separate raw-PTX signed regression | 8 cases;520 values and512 guards passed |
| Combined independent total | 14 cases;50,970 values and896 guards passed; only the first6 use fatbin |
| Genuine unsupported producer variants | Compressed PTX, duplicate PTX and nonempty JIT options each returned801 with null module output |
| Recovery and older profile | After rejections, a genuine nvFatbin container holding synthetic PTX7.0/sm_50 passed65 values and64 guards in the same context; counted separately |
| Rust workspace | 25 tests passed, including5 safe-decoder tests, C-input detection and actual GPU |
| Python suites | 15 loader/publication tests passed |

The independent fatbin-derived output buffers start with NaNs and include guards. Decoder tests cover every truncated prefix, shortened consistent outer lengths that reach inner parsing, overflowing/oversized fields, invalid metadata/flags, payload padding, record-count cap, opaque CUBIN skipping and2048 deterministic byte mutations. These are focused checks, not exhaustive fuzzing or fault-recovery coverage.

## Reproduce

Use the [M3c prerequisite commands](M3c-RESULTS.md#reproduce) to acquire pinned source/runtime/NVRTC/compiler headers in ignored cache directories, then add the official nvFatbin package without installation:

```powershell
python -m pip download --no-deps --dest .cache/reference nvidia-nvfatbin-cu12==12.4.99
$env:CARGO_INCREMENTAL = '0'
./scripts/run_m3d_smoke.ps1
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py' -v
```

The harness checks the wheel hash before loading its DLL, regenerates PTX and genuine positive/negative fatbins locally, builds the unchanged upstream host and checks aggregate outcomes. Public CLI staging is exercised as well. Raw output, producer binaries, source checkout, PTX, fatbins and executable remain ignored. None is redistributed in Git; only CT code, synthetic source tests and its own harness/docs are published.

## Scope

The [fatbin profile](compatibility/fatbin-profile.md) supports one uncompressed PTX module with measured Windows64 metadata. Compression, multiple-PTX linking/selection, runtime wrappers/registration, CUBIN execution, arbitrary nvcc output, CUDA Runtime/cudart, broad external applications, NVIDIA original/coexistence/performance comparison and AMD remain unsupported or unverified. The producer library's12.4 version does not raise CT's Driver lookup ceiling or imply CUDA12.4 conformance. System drivers, registry and global PATH remain unchanged. This is a bounded fatbin milestone, not full CUDA or M3/v0.1 clearance.
