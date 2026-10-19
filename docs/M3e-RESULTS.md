# M3e: compressed CUDA fatbin execution on Intel Arc

Validated 2026-10-19 on Windows x64 / Intel Arc B390. NVIDIA's unchanged
vectorAddDrv host executes a genuine compressed PTX fatbin through CT's
cuModuleLoadData, translation to SPIR-V and Intel Level Zero. CT uses its own
bounded Rust decoder, without vendor decoding libraries or kernel substitutions.

## Producer and preservation

The pinned source and NVRTC input match [M3c](M3c-RESULTS.md); NVIDIA
nvFatbin12.4.99 uses `-64 -cuda -host=windows -compress-all`. This is an adjusted
producer path using original source, not the original sample's entire nvcc
multi-architecture build. The staged executable and container remain byte-identical.
The producer may normalize PTX comments/padding; compiler input and decoded text
are distinct artifacts. Extracted plain and compressed PTX are byte-identical.

| Artifact in measured compressed run | SHA-256 / size |
| --- | --- |
| Compiler input PTX | `008525ca03e2c4bbeab02fc306ffefd37eaa45ca7bf2190d883cb5720b3cc03d` |
| Compressed fatbin | `564a858f17a7ed2d0564a6b494a2ea3c14026a341c06f3e72f528241d3a4f721`,1152 bytes |
| Preserved executable | `6ede3b7e90d5cd809dbed172a4887efd8dad95ee25a264afbb0bce6b1c83ba95` |
| nvFatbin wheel | `398b9ea66d888ae858e74935658dae5f9149fad0978b3ed55bb2d5113dec78fc` |

Executable/container hashes identify this run, not a reproducible-build guarantee.
The corresponding plain container is5232 bytes; packaging size is not a speed
benchmark. No NVIDIA execution/performance comparison was made.

## Observed checks

| Check | Result |
| --- | --- |
| Unchanged official host / public CLI with compressed fatbin | Both PASS; sample checks50,000 values |
| Independent compressed fatbin checks | 6 sizes1,63,64,65,257,50000;50,450 outputs and384 guards |
| Separate raw-PTX signed regression | 8 cases,520 outputs and512 guards |
| Renamed compressed subtraction kernel | 257 outputs,64 guards; PTX7.0/sm_50 |
| Invalid compressed declarations/stream/padding | 5 variants rejected with218/801 and null module output |
| Genuine duplicate PTX / nonempty options | Both rejected801 with null module output |
| Same-context recovery | Compressed older-profile add passed65 outputs and64 guards after rejections |
| Prior native regressions | M1:210 checks; M2:4 kernels/53 cases/606,660 outputs/4,992 guards; M3a:514 outputs/128 guards; M3b:80 queries/514 outputs/128 guards; M3c/M3d:official host and independent checks passed |
| Rust workspace | 28 tests passed including explicitly enabled GPU and real-producer checks |
| Python / lint | 15 loader/publication tests passed; workspace/all-targets Clippy passed with warnings denied |

The independent buffers start with NaNs and carry64 sentinel guards per case.
All extraction/semantic failures are reported before native module creation.
New synthetic compressed tests first failed with NOT_SUPPORTED, then passed.
Decoder checks include overlapping copies, extended literal/match lengths,
invalid/zero offsets, exact declared output length and caps, all truncated
prefixes of synthetic plain/compressed images, and4096 deterministic byte mutations.
These are bounded focused tests, not exhaustive fuzzing or full CUDA clearance.

## Reproduce and scope

Acquire pinned packages/source using [M3d prerequisites](M3d-RESULTS.md#reproduce):

```powershell
$env:CARGO_INCREMENTAL = '0'
./scripts/run_m3e_smoke.ps1
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py'
```

The smoke regenerates both local parity fixtures before the ignored Rust test.
Vendor packages, generated binaries, fatbins, PTX and raw logs remain ignored.
Only CT code, synthetic source tests, harness and documentation are published.

The [fatbin profile](compatibility/fatbin-profile.md) still accepts one module.
Multiple PTX selection/linking, wrappers/registration, CUBIN execution, arbitrary
nvcc formats, cudart/libraries, NVIDIA parity/coexistence and AMD are unverified
or unsupported. No API/version ceiling changed. System drivers, registry and
global PATH remain unchanged. The final goal remains a general CUDA translator.
