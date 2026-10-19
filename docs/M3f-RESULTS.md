# M3f: bounded PTX alternatives on Intel Arc

Validated 2026-10-19, Windows x64 / Intel Arc B390. CT now checks multiple known
PTX alternatives in one raw fatbin and chooses one before native module creation.
The current profile stays restricted: PTX7.0/sm_50 and PTX8.0/sm_52, one entry,
matching ordered argument kinds, different profiles. It is not module linking.

## Implementation

- A schema1 manifest lists26 exports, exact header signature IDs, resolver name/
  version intervals, bounded features and static source-test references.
  `check_compatibility_profile.py` checks consistency, not test execution.
- ct-fatbin returns bounded candidates with profile metadata. Limits:16MiB input,
  256 records,8 PTX candidates,256KiB PTX text per record,1MiB aggregate decoded/
  padded payload. Each declaration is charged before its decompression.
  This is not a bound on total process memory. The legacy single-extract API remains.
- The parser preserves the verified source profile through Kernel and Compiled.
  CUDA input handling compares metadata to the parsed body and validates every
  candidate before the sole native load call.
- Explicit priority:8.0/sm_52 over7.0/sm_50, independent of record order.
  Entry names and ordered ParamKind must match; parameter names need not match.
  Duplicate profiles and unknown profiles are rejected. A native load failure
  never triggers execution of a lower alternative.

## Actual GPU evidence

The unchanged baseline M3e DLL was built before Rust changes and preserved
locally with SHA-256
`f7c1cf40a6c8f202456fdc4def30f89f46349512664a80de3582957654c5aba9`.
The same two-candidate producer input returned801/null on that DLL and executed
successfully on M3f. NVIDIA nvFatbin12.4.99 is the genuine local producer; its
pinned wheel/source provenance follows [M3d](M3d-RESULTS.md).

Synthetic lower-profile PTX adds and upper-profile PTX subtracts. Both have the
same entry/argument kinds but different parameter names. Eight containers vary
record order, compression and two arbitrary entry names. Six sizes are tested
for each:1,63,64,65,257,50000. Independent CPU subtraction is the oracle, so merely
loading any candidate or replacing it with addition cannot pass. Output buffers
start with NaNs and carry64 sentinel guards per case. This tests selection,
not equivalence of computations between alternatives or NVIDIA selection parity.

| Check | Measured result |
| --- | --- |
| Alternative selection on real GPU | 48 cases;403,600 outputs and3,072 guards passed |
| Rejected alternatives | 6 cases; expected218/801 and null output |
| Same-context recovery | 65 outputs and64 guards passed after rejections |
| Repeated kernel execution | 100 cases,6,500 outputs and6,400 guards; separate from48 cases |
| Module creation/unload | 1,000 cycles passed; not a production endurance guarantee |
| Official NVIDIA vectorAddDrv / public CLI regression | Unchanged host/container passed50,000 values with both single-image and two-alternative compressed fatbins |
| Rust workspace | 36 tests including actual GPU and genuine compressed/plain producer parity passed |
| Python / static profile | 19 tests passed; signature/lookup/reference manifest validation passed |
| Lint / native ABI | Clippy all targets with warnings denied and rustfmt passed;12 C/Rust structures matched all size/offset/alignment fields |
| Earlier native regressions | M1:210 checks; M2:53 cases/606,660 outputs/4,992 guards; M3a/M3b loaders and official M3c/M3d hosts passed |
| Independent official compressed-fatbin regression | 6 sizes;50,450 outputs and384 guards |
| Separate raw signed-PTX regression | 8 cases;520 outputs and512 guards |

The six rejections cover duplicate profiles, different entry names, an extra
valid u32 parameter, an unsupported instruction in the unselected image,
metadata/body mismatch and unknown profile. The last two deliberately modify
producer output and are not claimed as unmodified NVIDIA-created variants.
Generated inputs, individual artifact hashes, binaries and raw logs remain local
and ignored. CPU fallback and per-kernel replacements are not used.

The official-host integration additionally packages a synthetic7.0 add fixture
and the unchanged original-kernel NVRTC8.0 output under their shared entry/ABI.
That genuine two-PTX container is1704 bytes, SHA-256
`939893615c1b2a4a209049da2254fe7801e5039181245689d4770ad2a0c4f434`.
The preserved host for that run has SHA-256
`372ea7367e8b252068d0517be4819f82fcf6dfa52b2184f4f8720a640dbaeac0`.
This is an adjusted input-packaging experiment, not the original nvcc build.
Both images add, so it proves application/CLI integration; the separate
add/sub experiment proves the selection rule. These additional50,450 independent
outputs/384 guards are not included in the48-case totals. The synthetic lower
image is test input, not a replacement injected by CT's translator.

## Validation and reproduction

Use pinned [M3d prerequisites](M3d-RESULTS.md#reproduce). Before changing the baseline
Rust source, preserve its built DLL and SHA-256 in ignored `.cache/m3f-baseline/`.
The native harness requires and checks that baseline for the RED comparison.
On an M3f-only clone, build commit4b0c64f in a separate checkout/output location;
do not reset an existing user's checkout. Synthetic/default tests need no vendor DLL.

```powershell
$env:CARGO_INCREMENTAL = '0'
python scripts/check_compatibility_profile.py
./scripts/run_m3f_smoke.ps1
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py'
cargo clippy --workspace --all-targets -- -D warnings
```

Unit checks include candidate count/aggregate cap boundaries, pre-decode rejection,
metadata/body profile, names/ABI/duplicate conflicts, unsupported lower candidates,
short C strings, raw PTX, wrappers/ELF rejection and prior decoder/parser checks.
The native official-host regression preserves application and asset bytes during staging.
External vendor tools are test producers, not CT runtime decoder dependencies.

SPIR-V Tools `spirv-val` was unavailable and that validator check is **skipped**.
Native Level Zero compilation/execution passed; it is a separate check.
NVIDIA original execution/selection, coexistence, AMD and full CUDA conformance
are unverified. Unknown-profile skipping, multiple entries, Runtime registration,
general linking and arbitrary nvcc containers remain future work. No API/version
ceiling changed. These measured totals are not inferred from the static feature manifest.

## Review

A fresh-context whole-branch review found no actionable findings and independently
passed Python19 tests and the default Rust suite. That reviewer did not rerun
native/ignored tests. A subsequent focused review of the official multi-image
integration delta also found no actionable findings. Native totals above are
from the implementation session's actual runs. Publication checks cover selected
files and all outgoing history; private artifacts remain ignored.
