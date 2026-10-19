# M3a: ordinary CUDA application loading through CT

Validated 2026-10-19 on the M2 Windows x64 / Intel Arc B390 environment. This is the first process-local loader increment, not full M3 or v0.1 release clearance.

Two independent synthetic C consumers use ordinary CUDA Driver ABI loading: one has a static `nvcuda.dll` import, the other uses `LoadLibrary("nvcuda.dll")` and `GetProcAddress`. Neither accepts a CT library path or contains CT-specific loading logic. The static import library is generated from the existing ABI declarations; the NVIDIA SDK was not installed or used.

The CLI copies the executable and explicitly supplied external PTX byte-for-byte into a fresh ignored directory, then supplies CT under the application-local name `nvcuda.dll`. No system DLL, original executable, global PATH or registry change occurs. Both consumers verify that the loaded driver is in their application directory without printing paths.

## Observed checks

- Normal dynamic CUDA loading without CT returned driver unavailable on this Intel-only environment.
- Both loading modes executed vector addition on the real GPU: 514 output values and 128 guards passed in total.
- Application and PTX bytes were identical before and after staging. The integration check verifies SHA-256 and byte equality; binaries are built once before both inspection and execution.
- Seven loader tests passed: PE import classification, unsupported CUDA symbols/cudart rejection, x86/DLL/delay/ordinal rejection, truncated/unmapped PE and invalid IAT rejection, staging collisions/identity, child argument/exit handling and CLI input-path redaction.
- Existing six publication-guard tests passed. M2's 53 cases / 613,056 checks and M1's 210 checks passed again. Rust formatting and clippy with warnings denied passed.
- Independent review identified a missing IAT bounds check and argparse input-path disclosure. Both were reproduced with failing regression tests, corrected and independently rechecked.

## Use

Developer prototype requires Python 3.10+, Windows x64, the CT workspace and a built trusted `ct_cuda.dll`. The GPU check also requires Rust MSVC, MSVC C++ tools and Intel Level Zero.

```powershell
python scripts/ct.py inspect path/to/application.exe
python scripts/ct.py run --ct-dll target/debug/ct_cuda.dll --ptx path/to/kernel.ptx path/to/application.exe -- kernel.ptx
./scripts/run_m3_smoke.ps1
python -m unittest discover -s tests -p 'test_*.py' -v
```

Arguments after `--` belong to the application. Its working directory is the fresh bundle; only explicitly supplied PTX files accompany it. Bundles persist locally in ignored `.cache/runs/` for diagnosis. Native smoke builds use fresh ignored `.cache/m3-build/` directories so reruns do not overwrite possibly held import-library files. The CLI prints hashes and triage results, not local paths. Child stdout/stderr belongs to the application and may contain its own private output; never publish raw output without review. Child exit codes are propagated.

## Remaining gaps

This tests synthetic standalone applications using the restricted M2 PTX profile. It does not demonstrate an external application or NVIDIA SDK-built binary working unchanged. Static unsupported CUDA symbols are rejected, while dynamically requested symbols cannot be established from the import table. `inspect` reports compatibility as unproven.

Absolute System32 loading, altered DLL search policies, delay imports, ordinal CUDA imports, versioned `cuGetProcAddress`, CUDA Runtime/cudart, additional application-local dependencies and general fatbin/library/AI workloads are unsupported. `ct doctor` and broader diagnostics remain future work. The launcher executes trusted applications; PE inspection is not an executable safety assessment.

NVIDIA original execution and coexistence were not tested; no NVIDIA hardware was available. Matching staged hashes establishes preservation of the tested binaries, not the cross-vendor comparison required for full M3. AMD remains unimplemented. See [fixed project direction](CUDA-CONNECTION.md) and [M2 PTX limits](compatibility/ptx-profile.md).
