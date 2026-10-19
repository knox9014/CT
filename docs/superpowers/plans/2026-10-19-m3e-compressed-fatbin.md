# M3e: bounded compressed PTX fatbin execution

Goal: connect unchanged CUDA Driver applications to CT on Intel/AMD GPUs.
This increment extends container decoding, without kernel-specific replacements.

1. Add failing tests for compressed PTX, overlapping LZ4 matches, extended
   lengths, truncation, invalid offsets, declared-size mismatch and output caps.
2. Implement bounded block decompression in ct-fatbin; return borrowed plain
   PTX or owned decoded PTX. Preserve all metadata checks and the one-module
   rule. Integrate the owned result into cuModuleLoadData.
3. Run genuine nvFatbin compressed/uncompressed parity checks and unchanged
   NVIDIA vectorAddDrv on Arc. Check output and guards independently, malformed
   inputs and recovery, renamed kernel semantics, and earlier regressions.
4. Document measured scope, run privacy scans and fresh branch review, and
   publish a stacked draft PR. Do not merge main.

Constraints: maximum image 16 MiB; decoded PTX including terminator/padding
   at most MAX_PTX_SIZE + 8, checked before allocation. Exact declared decoded
   length and canonical compressed payload padding required. No dependencies,
   raw logs, vendor binaries, private paths or credentials published.

Ruling: multiple PTX variants are deferred to the next increment. Their
selection requires a separately specified module/ABI policy; compression can
be verified independently without guessing how to combine modules.

Validation: synthetic decoder tests; ignored real-producer parity test;
workspace Rust and Python suites; M3e native smoke and existing native scripts.
No full CUDA compatibility, CUBIN execution, cudart or AMD claim.
