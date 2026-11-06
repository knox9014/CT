# CT (Cuda Translater)

[한국어](README.md) · **English**

**CT is a project to run existing CUDA programs on Intel GPUs you already own.**

When a CUDA program offloads computation to a GPU, it calls the CUDA driver. CT handles those calls, translates supported GPU code (PTX) into SPIR-V, and runs it through Intel Level Zero.

```text
CUDA program → CT's CUDA driver interface → PTX translated to SPIR-V → Intel GPU
```

**The current focus is Windows x64 and Intel Arc B390.** An AMD backend is a later goal, after validating real applications on Intel.

## What we've verified

| Area | Result |
| --- | --- |
| GPU computation | Selected CUDA kernels, including vector addition, ReLU, and matrix multiplication, ran on Arc B390 and passed numerical checks. [Kernel validation](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/M2-RESULTS.md) |
| Official NVIDIA sample | We made an experimental build from the original host and kernel sources of `vectorAddDrv`. CT ran a CUDA container (fatbin) with compressed PTX, and we verified 50,000 results. [Build and results](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/M3e-RESULTS.md) |
| CUDA application compatibility | CUDA Runtime initialization is still under investigation. Real array operations with the distributed CuPy package and general CUDA application execution have yet to be verified. |
| Other GPUs | Testing was performed on Intel Arc B390. Other Intel models and AMD GPUs are future validation targets. |

## User guide

You can build CT from source and run validation examples on Windows x64 with an Intel Arc B390. The commands below use a public development commit. The default branch on GitHub contains the project documentation; the checkout step below gets the runnable code.

### 1. Set up your environment

- Install the Intel graphics driver. CT uses Level Zero from this driver.
- Install Git and Python 3, then check that `git --version` and `python --version` work in PowerShell 7. [Download Python](https://www.python.org/downloads/windows/)
- In Visual Studio Build Tools, install the **Desktop development with C++** workload, including the MSVC x64 tools and the Windows SDK. [Download Visual Studio](https://visualstudio.microsoft.com/downloads/)
- Install Rust for Windows MSVC with rustup, then run `cargo --version` in a new PowerShell session. [Install Rust](https://rustup.rs/)

```powershell
git clone https://github.com/knox9014/CT.git
cd CT
git checkout --detach d57659f6a64d7fb211130de45a896654cce40738
```

### 2. Check that your Intel GPU works

```powershell
cargo run --quiet --bin ct-intel-smoke
```

CT uses the first Intel GPU that Level Zero finds. In the final JSON output, look for `"status":"pass"` and check the actual GPU name in `device`. This step tests the Intel execution environment with a SPIR-V example included in the repository. [Intel smoke test](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/M0-RESULTS.md)

To select a specific GPU when several Intel GPUs are available, add part of the model name after the example file path. For instance, `cargo run --quiet --bin ct-intel-smoke -- tests/fixtures/vector_add.spv B390` selects the B390.

### 3. Check that CUDA calls run through CT

```powershell
pwsh -NoProfile -File scripts/run_m3_smoke.ps1
```

The script builds CT and two CUDA test programs and runs them on the Intel GPU. In the final JSON output, check for `"status": "pass"` and `"results": 514`. [CUDA Driver connection test](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/M3a-RESULTS.md)

### 4. Check your own program

Replace the paths below with a trusted Windows x64 executable and the PTX file it loads. Start with `inspect` to see which CUDA functions the executable imports. Static inspection alone cannot identify functions resolved dynamically or verify that GPU computations will work.

```powershell
python scripts/ct.py inspect "C:\path\to\app.exe"
cargo build -p ct-cuda
python scripts/ct.py run --ct-dll target/debug/ct_cuda.dll --ptx "C:\path\to\kernel.ptx" "C:\path\to\app.exe" -- kernel.ptx
```

Arguments after `--` are passed to the program. This example assumes the program accepts `kernel.ptx` as an argument. CT copies the executable and the specified GPU code into a run directory under `.cache/runs/`, where the program uses CT as `nvcuda.dll`. This example targets a standalone program that loads external PTX. [Driver API coverage](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/compatibility/driver-api.md) · [Reproduce the official sample test](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/M3e-RESULTS.md)

### Troubleshooting

| Symptom | What to check |
| --- | --- |
| `link.exe` is missing or an MSVC error occurs | Check that the C++ workload and Windows SDK are installed, then open a new PowerShell session. |
| No GPU is found | Check that the Arc B390 appears in Device Manager and verify the Intel graphics driver. |
| `unsupported static CUDA symbol` or `CUDA Runtime imports are unsupported` | The program is outside the supported Driver execution path described above. Check the error and the CUDA functions it requires. |

When reporting a problem, include your GPU model, Windows version, steps to reproduce, and error message. Remove personal paths from any logs you share. [Guidelines for public artifacts](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/PUBLICATION.md)

## Next goals

1. Run one real CUDA application as distributed on Intel and complete its workload.
2. Compare the results with a run on NVIDIA's official driver using the same input.
3. Reproduce setup and execution on another Intel PC, and document performance and limitations.
4. Add an AMD backend based on what we learn from Intel validation.

[Development roadmap and release criteria](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/CT-EXECUTION-ROADMAP.md) · [Driver API coverage](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/compatibility/driver-api.md) · [PTX coverage](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/compatibility/ptx-profile.md)

## License

CT is distributed under the [MIT License](LICENSE). You may use, modify, and redistribute it for personal or commercial purposes. Include the copyright and license notices when distributing copies or substantial portions of the software. Third-party materials retain their own licenses.
