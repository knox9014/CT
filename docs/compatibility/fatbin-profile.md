# Experimental raw fatbin profile through M3k

CT can extract bounded plain or LZ4-compressed alternative PTX images from a raw CUDA fatbin passed to `cuModuleLoadData`. The runtime decoder is the dependency-free Rust `ct-fatbin` crate. NVIDIA's nvFatbin library is only a local test producer; CT does not load it to decode or execute images. M3f selects one known-profile image; it does not link modules.

## Accepted envelope

- Little-endian raw magic `0xba55ed50`, outer version1, fixed16-byte outer header; exact declared total size for slice/file inspection.
- At most16MiB image and256 records. Records have version0x0101, an 8-byte-aligned header of64..4096 bytes and a positive, 8-byte-aligned payload length fully inside the image.
- At most8 PTX records (kind1); aggregate decoded/padded bytes at most1MiB, charged before each decompression. The CUDA selector requires distinct known profiles, currently allowing at most two successful alternatives. Bounded opaque CUBIN records (kind2) can be skipped; NVIDIA machine code is never executed. The legacy Rust `extract_ptx` wrapper still requires exactly one record.
- PTX metadata must identify a supported pair: PTX7.0/sm_50 or PTX8.0/sm_52; embedded PTX is independently parsed. The observed64-bit CUDA/Windows flags are `0x45` for plain or `0x2045` for compressed. Reserved bytes44..56 must be zero. Plain records require zero compressed and decoded sizes.
- Compressed records declare a positive actual compressed size at byte16 and decoded u64 size at byte56 of the record header. The compressed stream must fill its payload except for at most7 zero alignment bytes. A bounded raw LZ4 decoder handles literals, extended lengths and overlapping matches; decoded size must be exact and at most262152 bytes (256KiB PTX plus terminator/alignment), checked before allocation. Invalid offsets, truncated sequences, declared-size mismatches and nonzero padding are rejected. LZ4 frame format and other compression schemes are unsupported.
- Bounded identifier and option-descriptor fields follow the measured nvFatbin12.4 layout. Identifier bytes must be ASCII with valid termination/padding. Nonempty JIT options are unsupported. Empty options must reference valid zero-filled header space.
- PTX payload is nonempty ASCII, at most256KiB before a NUL terminator, with only zero bytes afterward. Extracted PTX then passes the ordinary [PTX parser/profile](ptx-profile.md); extraction does not imply support for arbitrary instructions.

This profile is verified against genuine NVIDIA nvFatbin12.4.99 output and compared with the primary [LLVM20.1.8 implementation](https://github.com/llvm/llvm-project/blob/llvmorg-20.1.8/clang/lib/Interpreter/DeviceOffload.cpp). It is an experimental, version-bounded format interpretation, not a NVIDIA guarantee of binary-format stability or every fatbin layout.

## Rejection and C-pointer contract

Every candidate must parse/type-check and its metadata must match its PTX body. Metadata/body mismatch, malformed ranges/streams, missing terminators or nonzero padding map to INVALID_PTX=218. Recognized unsupported versions/flags, resource caps, duplicate profiles, differing complete entry-name/ordered-(ParamKind,alignment) maps, nonempty options, unknown profiles and images without PTX map to NOT_SUPPORTED=801. Entry order and parameter names may differ. Errors stop at the first detected extraction or compilation/selection error; a global precedence among errors in multiply invalid input is not promised. Outputs are cleared before failure; valid contexts remain usable after parse/selection failures.

Priority is explicitly8.0/sm_52 above7.0/sm_50, independent of record order. All candidates must be understood; unknown-profile skipping is not implemented. Shared entry-name/ABI map is not proof of equivalent computation; the caller supplies alternative images, and CT chooses one under this policy without concatenation or semantic-equivalence claims. Only the selected image reaches native module creation; native failure does not retry a lower profile. No device compute capability or newer CUDA version is advertised by this policy.

`cuModuleLoadData` supplies no byte length. A caller must provide a readable PTX C string or, for raw fatbin magic, a readable fixed header and the entire image for an accepted declared size. The cap is checked before forming the full binary slice. Pure byte-slice tests cover truncated files; arbitrary short/invalid non-null host pointers cannot be safely validated through this C ABI. Runtime wrapper magic `0x466243b1` is rejected without following its embedded pointers. Raw ELF input is unsupported.

The launcher accepts binary `.fatbin` assets after checking their outer header, exact actual length/alignment and cap. That is staging triage; CT performs full record/semantic validation. Historical ASCII PTX under a `.fatbin` filename remains accepted for M3c regression. The CLI's existing `--ptx` asset option accepts either form; it does not unpack/rewrite the file before launching.

## Current exclusions

General multi-profile selection, module linking, LTO-IR, unknown record kinds, runtime wrappers, CUDA Runtime registration, CUBIN execution, general nvcc-produced formats and NVIDIA parity/coexistence remain outside this increment. Duplicate-profile and JIT-option containers are rejected. Mixed CUBIN skipping is byte-bounds tested with synthetic opaque data; no NVIDIA machine code execution is claimed. See historical [M3d results](../M3d-RESULTS.md), [M3e results](../M3e-RESULTS.md), [M3f results](../M3f-RESULTS.md) and current [M3g results](../M3g-RESULTS.md). Decoder sequences follow the primary [LZ4 block format](https://github.com/lz4/lz4/blob/v1.10.0/doc/lz4_Block_format.md); real-producer parity and GPU checks establish the tested NVIDIA container profile, not every LZ4 producer/layout.

M3g permits1..32 entries per image in the restricted PTX profile, producing one native module. Alternative images must expose the same entire entry map; they are selected, never linked. Used globals/device calls remain unsupported.

M3k includes pointer/scalar kind and alignment in the complete ABI identity; changing4-byte to8-byte pointer requirements across alternatives is rejected. See [M3k evidence](../M3k-RESULTS.md).
