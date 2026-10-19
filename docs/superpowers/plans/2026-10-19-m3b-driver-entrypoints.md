# M3b Versioned Driver Entry Points Implementation Plan

> Execute inline with superpowers:executing-plans, test-first implementation and final independent review.

**Goal:** Connect CUDA callers using the four-argument cuGetProcAddress and five-argument cuGetProcAddress_v2 to CT's implemented Driver functions with correct ABI selection.

**Spec:** `docs/CUDA-CONNECTION.md`, M3 follow-up. User authorized continued incremental development; preserve unchanged application/PTX bytes and privacy-safe publication.

**Architecture:** A static Rust lookup table maps canonical CUDA base names and verified ABI version intervals to CT function addresses. Both exported resolvers share lookup logic but use their distinct missing-symbol return contracts. No GPU context/initialization is needed to obtain addresses. Official NVIDIA 12.0 headers provide an independent ABI and typed C consumer check, downloaded without installation into ignored local cache.

## Fixed contracts

- Add exactly `cuGetProcAddress` (four arguments, 11.3 ABI) and `cuGetProcAddress_v2` (five arguments, 12.0 ABI), bringing exports to 26.
- Queries use canonical base names, not `_v2`/`_v3` export spellings. Match verified typedef version floors. `cuCtxCreate` resolves the three-argument v3020 only below 11040; newer signatures are unsupported. Never return an incompatible pointer.
- `cuGetProcAddress` base lookup selects its four-argument ABI at 11030..11999 and five-argument ABI at 12000. CT's lookup ceiling is 12000; higher requests return NOT_SUPPORTED, without advertising a CUDA driver version.
- Support flags 0/default and 1/legacy; recognized per-thread flag2 returns NOT_SUPPORTED; invalid flag combinations return INVALID_VALUE. No per-thread stream conformance claim.
- Missing/ABI-unavailable requests return NOT_FOUND=500 from the old resolver; the new resolver returns SUCCESS with null pointer and status1/missing or2/version unavailable. Initialize valid output storage before rejection. Null required arguments and nonpositive versions return INVALID_VALUE. Optional status pointer may be null.
- Function addresses point to existing CT implementations, whose documented feature/error limitations remain in force. DriverGetVersion continues returning NOT_SUPPORTED and zero.
- Trusted caller pointers must be valid. No raw symbols, personal paths or native build logs published.

## Tasks and review focus

- [x] Add failing Rust resolver tests for every table entry's floor, upper boundary, symbol aliases, null arguments, status outputs, flags, reentrant calls and resolver self-selection. Implement shared lookup and exports.
- [x] Extend the ABI header and import allowlist through its existing shared macro. Add a C consumer compiled solely against official CUDA headers, obtaining all CUDA functions through each resolver and executing restricted PTX on Arc B390. Verify typed ABI assignments at compile time.
- [x] Extend smoke script with hash-checked NVIDIA headers and fresh build directory; prove byte-identical staging and real GPU outputs/guards in both resolver modes. Keep ordinary static/dynamic loading tests.
- [x] Run Rust workspace including real GPU, Python suites, M1/M2/M3 regressions, formatting/clippy and independent review. Reproduce and fix material findings before publication.
- [ ] Document version/flag/error policy, exact results and unresolved external-app/NVIDIA/AMD gaps; scan staged/tracked/history, commit and open stacked draft PR.

## References

NVIDIA CUDA 11.8 and 12.0 Driver Entry Point Access documents differ in missing-symbol behavior. Pinned official PyPI distribution: nvidia-cuda-runtime-cu12 12.0.107, win_amd64 wheel SHA-256 `f595d66142e9ba5d1157d73ef06488735d814415a462714426f3989344e675eb`; cuda.h `aa801e582dc7cc251bb7d7d84eebce0a852f4162f272dc40ae33c21cc2a0afba`; cudaTypedefs.h `d0691e868dea2108237a899e2c1e9685cc7bd4d7d68f63b0c6b3df2a7ceb4774`. Headers remain ignored; no vendored NVIDIA code is committed.

## Execution ledger

- Rust resolver imports failed before implementation; all three resolver tests then passed. Native C application compiled with official headers but failed exit42/missing exports against the old M3a DLL; new M3b DLL passed both modes, 80 queries / 514 results / 128 guards.
- All 16 Rust tests including GPU and all 13 Python tests passed. M1/M2/M3a and 12-structure ABI oracle passed again; formatting/clippy passed.
- Independent reviewer verified all ABI floors against pinned typedefs, reviewed contracts and independently reran the three resolver tests. No actionable findings.
- Ruling: retain narrow lookup ceiling12000 and explicitly reject flag2 — unsupported versions/stream semantics must not be advertised — costs compatibility with callers that request them.
- Ruling: use MSVC external-header warning handling and UTF-8 for unchanged vendor headers — vendor anonymous unions/comments caused unrelated warnings — CT consumer source still compiles with /W4 /WX.
- Local sandbox denied MSVC import-library replacement; the same build/test commands passed outside the sandbox. No system configuration changes were made.
