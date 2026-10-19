# Experimental M3d raw fatbin profile

CT can extract one uncompressed PTX module from a raw CUDA fatbin passed to `cuModuleLoadData`. The runtime decoder is the dependency-free Rust `ct-fatbin` crate. NVIDIA's nvFatbin library is only a local test producer; CT does not load it to decode or execute images.

## Accepted envelope

- Little-endian raw magic `0xba55ed50`, outer version1, fixed16-byte outer header; exact declared total size for slice/file inspection.
- At most16MiB image and256 records. Records have version0x0101, an 8-byte-aligned header of64..4096 bytes and a positive, 8-byte-aligned payload length fully inside the image.
- Exactly one uncompressed PTX record (kind1). Bounded opaque CUBIN records (kind2) can be skipped; NVIDIA machine code is never executed. Multiple PTX records are rejected, rather than guessed/concatenated/linked.
- The PTX metadata must match a supported pair: PTX7.0/sm_50 or PTX8.0/sm_52. The accepted flags value is the observed64-bit CUDA/Windows producer profile `0x45`; compressed size and reserved compression fields must be zero.
- Bounded identifier and option-descriptor fields follow the measured nvFatbin12.4 layout. Identifier bytes must be ASCII with valid termination/padding. Nonempty JIT options are unsupported. Empty options must reference valid zero-filled header space.
- PTX payload is nonempty ASCII, at most256KiB before a NUL terminator, with only zero bytes afterward. Extracted PTX then passes the ordinary [PTX parser/profile](ptx-profile.md); extraction does not imply support for arbitrary instructions.

This profile is verified against genuine NVIDIA nvFatbin12.4.99 output and compared with the primary [LLVM20.1.8 implementation](https://github.com/llvm/llvm-project/blob/llvmorg-20.1.8/clang/lib/Interpreter/DeviceOffload.cpp). It is an experimental, version-bounded format interpretation, not a NVIDIA guarantee of binary-format stability or every fatbin layout.

## Rejection and C-pointer contract

Malformed ranges, missing terminators or nonzero text padding map to INVALID_PTX=218. Recognized unsupported versions, flags, compressed/multiple PTX, nonempty options, unsupported profiles and images without PTX map to NOT_SUPPORTED=801. Outputs are cleared before failure; valid contexts remain usable after these parse failures.

`cuModuleLoadData` supplies no byte length. A caller must provide a readable PTX C string or, for raw fatbin magic, a readable fixed header and the entire image for an accepted declared size. The cap is checked before forming the full binary slice. Pure byte-slice tests cover truncated files; arbitrary short/invalid non-null host pointers cannot be safely validated through this C ABI. Runtime wrapper magic `0x466243b1` is rejected without following its embedded pointers. Raw ELF input is unsupported.

The launcher accepts binary `.fatbin` assets after checking their outer header, exact actual length/alignment and cap. That is staging triage; CT performs full record/semantic validation. Historical ASCII PTX under a `.fatbin` filename remains accepted for M3c regression. The CLI's existing `--ptx` asset option accepts either form; it does not unpack/rewrite the file before launching.

## Current exclusions

Compressed PTX/decompression, multiple-PTX selection/linking, LTO-IR, unknown record kinds, runtime wrappers, CUDA Runtime registration, CUBIN execution, general nvcc-produced formats and NVIDIA parity/coexistence are outside this increment. Genuine compressed, duplicate-PTX and JIT-option containers were tested for explicit rejection. Mixed CUBIN skipping is byte-bounds tested with synthetic opaque data; no NVIDIA machine code execution is claimed. See [M3d results](../M3d-RESULTS.md).
