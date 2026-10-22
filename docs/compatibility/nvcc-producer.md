# Reproducible nvcc12 diagnostic producer

This recipe compiles CT-owned source without executing its CUDA program. It
authenticates NVIDIA/STL archives, snapshots the installed host-tool/header/library
closure, and independently compares compressed/plain PTX. It does not establish
Runtime kernel support or release readiness.

Download the official Windows x86_64 archives from NVIDIA's
[CUDA12.0.0 redistribution manifest](https://developer.download.nvidia.com/compute/cuda/redist/redistrib_12.0.0.json):
cuda_nvcc12.0.76, cuda_cudart12.0.107 and cuda_cccl12.0.90. Save them locally
as `cuda_nvcc.zip`, `cuda_cudart.zip`, `cuda_cccl.zip` in an ignored directory.
Obtain the original [Microsoft STL commit](https://github.com/microsoft/STL/tree/ab600751924207014ab02f7422ee00a6843e2f0f)
archive from GitHub and save as `stl.zip`. The script and toolchain lock pin all
four archive hashes; mismatched archives are rejected before extraction/execution.
No vendor header is patched or published in CT.

From the repository root, with the installed VS x64 environment script supplied:

```powershell
python scripts/prepare_nvcc_probe.py prepare --output .cache/p09a2-producer --packages .cache/p09a2-probe --host-profile diagnostic --vcvars "$env:CT_VCVARS"
python scripts/prepare_nvcc_probe.py replay --manifest .cache/p09a2-producer/manifest.json
$env:CT_NVCC_COMPRESSED = "$PWD/.cache/p09a2-producer/keep-compressed/vector.fatbin"
$env:CT_NVCC_PLAIN = "$PWD/.cache/p09a2-producer/keep-plain/vector.fatbin"
cargo test -p ct-fatbin --test decoding genuine_nvcc_compressed_and_plain_match -- --ignored --exact
```

The compiler flags are `--cudart=shared --cudadevrt=none --keep --generate-code
arch=compute_52,code=compute_52 -Xcompiler /utf-8`, with separate keep directories
and an additional `--no-compress` for the plain mode. Diagnostic mode explicitly
adds `-allow-unsupported-compiler` and original STL17.8 headers. Source, commands,
archive members, host tools and complete local include/library/bin inventories,
EXEs, generated stubs, PTX and raw fatbins are bound in the local manifest.
Replay rebuilds expected archive-member hashes rather than trusting child output.
Replay also requires actual compressed0x2041 and plain0x41 flags in the respective
artifacts. Preparation removes NVCC flag/host-selector variables and CL/LINK and
other implicit compiler include/flag variables, records the normalization policy,
and explicitly selects the recorded host compiler directory with `--compiler-bindir`.
Compiler/linker tools must share that directory, which is first on the normalized
PATH. Include/library inventories describe the resulting VS environment.

NVIDIA and STL files are authenticated against pinned archives. Installed MSVC
and Windows SDK files are local provenance snapshots, not authenticated vendor
package claims. A hash snapshot cannot qualify an unsupported compiler. Qualified
mode rejects the override and requires MSVC19.3x plus a separately reviewed
supported-host compiler hash pin; none is currently registered. Its actual compatibility
with this source must then pass compilation. The current installed19.51 host is
diagnostic only. A missing supported host remains unverified.

All generated files and manifests, including absolute local paths and logs, stay
under `.cache/`. Public summaries report classifications and hashes, never raw
manifest/log content. Replay audits artifacts; native numerical execution is a
separate P09a2-B gate.
