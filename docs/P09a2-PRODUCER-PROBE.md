# P09a2 producer preflight: real nvcc inputs and current boundaries

Observed 2026-10-22. Product execution code remains the P09a1 candidate
`24ef127a8eaf813e4918c1ec091b5aa359a90166`.
P09a1 PR27 hosted CPU/validator CI39730622022 completed successfully.
This document records a throwaway local probe, not a new required Runtime lane.

## Authenticated producer inputs

The [NVIDIA CUDA12.0.0 component manifest](https://developer.download.nvidia.com/compute/cuda/redist/redistrib_12.0.0.json)
provided these Windows archives. All downloaded byte sizes and SHA-256 values
matched that manifest. Components were extracted into an ignored local toolkit;
no system driver, global environment or installed Visual Studio was changed.

| Component | Version | Archive bytes | SHA-256 |
| --- | --- | --- | --- |
| cuda_nvcc | 12.0.76 | 58899378 | f67406f44263f0e4a110a8cf0200bff1d3d0e32917db8a7c9e417a87eb7ca372 |
| cuda_cudart | 12.0.107 | 2267147 | 1cd8516feee068c6d718453e76b0dfcbee27844a35d4f3aa608a3d316190309c |
| cuda_cccl | 12.0.90 | 2608382 | dd422d4cc8462d112411659a56cc78cb6010d704f83db3e48c55a3f66eed5ec2 |

The executable reports nvcc12.0.76/build compiler.31968024_0. Its SHA-256 is
`6f0418e46a3f530d964bb6fb944e5dd43d3ab2046e4a2212991d0cf7bfcecbd7`.
PE FileVersion is not the nvcc compiler version and was not used for identification.

## Host limitation and diagnostic compilation

Only MSVC19.51 was found installed. The normal nvcc build rejected that host
version. CUDA12.0's [published Windows compiler table](https://docs.nvidia.com/cuda/archive/12.0.0/cuda-installation-guide-microsoft-windows/index.html)
lists MSVC193x/192x/191x, not this installed compiler.

An override-only attempt also failed against the newer installed STL. A diagnostic
build then used `-allow-unsupported-compiler`, original Microsoft STL17.8 headers
selected through a local include directory, and `/utf-8`. All251 selected STL
files matched their archive entries and pinned Git blob identities at Microsoft
commit `ab600751924207014ab02f7422ee00a6843e2f0f`
([official release](https://github.com/microsoft/STL/releases/tag/vs-2022-17.8)).
STL archive SHA-256:
`ad92513bf0d77d544dad3a1a9f1b94152c4bdc9f7338475ece01657495b977c6`.
Header bytes were not patched. This is a custom header selection with an
unsupported host, not a qualified NVIDIA/MSVC combination. C4828 warnings remained.

VS17.8/17.6/17.4 channel discovery returned manifest bytes that did not match the
corresponding channel hashes/sizes. Those manifests and their package metadata
were not used to download or execute an MSVC toolchain. Supported-host producer
qualification remains unverified; the mismatch cause is unresolved.

The CT-owned source compiled an unsigned integer vector addition with seventeen
elements and a `<<<2,16>>>` launch. `--cudart=shared` and PTX-only compute52 were
used. The default device-runtime build, `--cudadevrt=none` variant and an additional
`--no-compress` variant all produced host executables with the diagnostic setup.
They are source-built fixtures, not original third-party distributed programs.

## Constructor observations

PE import inspection and a throwaway CPU-only observer showed:

| Producer | Fatbin callbacks | Function callbacks | Variable callbacks | End/unregister |
| --- | --- | --- | --- | --- |
| default device runtime | 2 | 33 | 11 | 2 / 2 |
| `--cudadevrt=none` | 1 | 1 | 0 | 1 / 1 |

The observer is deliberately nonfunctional: it returns801/null at the first
allocation and both unchanged executables exit11 before kernel launch. It does
not execute through CT, and its callback counts prove neither Runtime correctness
nor CUDA initialization equivalence. It is not production code or a reusable
implementation. The generated host stub and original headers independently show
constructor binary/function/end registration, atexit unregister, TLS call-config
pop, and launch by host-function address plus argument-storage pointers.

The nodevrt executable imports7 functions beyond P09a1's14-entry profile:
`__cudaRegisterFatBinary`, `__cudaRegisterFatBinaryEnd`,
`__cudaRegisterFunction`, `__cudaUnregisterFatBinary`,
`__cudaPushCallConfiguration`, `__cudaPopCallConfiguration`, `cudaLaunchKernel`.
The default executable additionally imports and actually calls `__cudaRegisterVar`.
Thus prospective profiles have21 and22 exports respectively, not already
implemented support. Both executables are currently rejected by CT's Runtime
import whitelist.

The first wrapper has magic0x466243b1/version1 and a592-byte raw payload.
The second default wrapper has version2 and zero bytes in its own raw payload,
but its extra field points to a null-terminated array of prelinked raw fatbins.
It is not an empty/no-op module. Manufacturer link.stub and callback observations
agree that the extra device-runtime registrations must be accounted for.
No private function-name exception is an acceptable implementation.

## Container and lower execution path

The compressed nvcc container is608 bytes: raw fatbin version1/header16,
record version0x101/header72, flags0x2041, compressed bytes516, padded bytes520.
The no-compress variant is1080 bytes with record header72/flags0x41.
Current CT only recognizes the separately observed nvFatbin12.4 metadata profile;
accepting a new flag alone cannot handle the nvcc header's missing option descriptor.
Direct `cuModuleLoadData` of the original compressed container returned801.
An independent throwaway LZ4 decoder produced985 bytes from the compressed record;
adding only its zero alignment padding matched the992-byte uncompressed record
payload byte-for-byte. Decoded SHA-256:
`dbc2a34b7d879baf1e066b1cb8daf519baa145c41d22c732e9ab70944fcc58b9`.
This validates the observed payload relationship, not product decoder acceptance
or general nvcc compression compatibility.

Original standalone PTX translated through CT without modification; actual
SPIRV-Tools validation passed for OpenCL1.2. A throwaway direct-Driver consumer
then executed that PTX on Arc B390:17 expected results,4 output guards and168
input bytes preserved. This bypassed the executable's Runtime host stub and the
currently unsupported raw container. It establishes the bounded lower PTX path,
not P09a2 Runtime application execution.

| Observed artifact | SHA-256 |
| --- | --- |
| CT-owned probe source | 68bc6a37fa96decb5dd2ece14f6940561f63b079e07c726f2ff057b6f5327949 |
| default diagnostic EXE | b15a2cf27359ffc77961ae8eb0ba950c10ef371b4aceb2bebce76faec4764594 |
| original PTX | a604f16a4358dad0a825992d8f739b1608ee854044799521062a6d298cad26e6 |
| compressed raw fatbin | 543ffa4fd15cc8727aabefd1b9f18d977c4a5a74c49b1d8f32309ca542d8290f |
| uncompressed raw fatbin | 9b038171a6373d3c0dddf556a98680b0aca8b1674ff035b1f1ea1912d9d85b88 |

An independent read-only audit matched archive/source/artifact hashes, all251 STL
files, both observed EXE hashes and constructor counts. It found the additional
metadata-shape limitation and confirmed the distinction between callback evidence,
Driver execution and unimplemented Runtime execution. It did not run programs/GPU.

Temporary source, generated vendor-containing files, binaries, paths and raw logs
remain ignored. These hash records are not a complete public reproducible producer
recipe. The implementation stage must add CT-owned public fixtures and a pinned
recipe, distinguish diagnostic and qualified producer lanes, and preserve original
EXE/fatbin bytes in native Runtime verification.
