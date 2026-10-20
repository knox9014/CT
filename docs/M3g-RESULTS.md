# M3g / P02: several CUDA kernels in one native module

Validated 2026-10-19, Windows x64 / Intel Arc B390. CT now parses multiple kernel
entries in one PTX source, emits a single SPIR-V module and creates one Level Zero
module with several kernel handles. CUDA function tokens select that module's
entry and its own argument ABI. No per-kernel replacement or CPU fallback is used.

## Accepted scope

- PTX7.0/sm_50 or8.0/sm_52; source256KiB and65536 tokens per module,1..32 visible
  entries with distinct names. Current register256/block128/instruction4096/param32
  bounds apply per entry. Registers, labels and parameters are independently scoped.
- Unused globals are still validated before all entries; used global storage,
  constant lookup and device calls remain unsupported. No common global storage
  semantics are claimed by this milestone.
- The new parse_module/translate_module APIs support modules. Legacy parse/translate
  still require a single entry, preserving their return-type contract.
- SPIR-V IDs are global across functions. Function types/constants/builtin globals
  are shared; per-function register/label state is distinct. Each entry lists only
  its used builtins in its interface.
- A native module owns every kernel handle. Partial creation retains any returned
  handles before cleanup; kernel destruction precedes module destruction. Uncertain
  cleanup poisons context and retains resources under the existing policy.
- Alternative images require identical complete entry-name -> ordered ParamKind maps.
  Entry order and parameter names may differ. The existing explicit known-profile
  rank, metadata/body checks, resource caps and no-native-fallback rule remain.
- Pointer(global f32,8-byte argument,4-byte data alignment), U32/F32(4-byte argument)
  remain the ABI kinds. Structures/vectors/other address spaces require later work.
  Synchronous1D launch and26 CUDA exports are unchanged.

## Measured native checks

The public synthetic multi_entry.ptx contains add/sub kernels with four arguments
and a scalar fill kernel with three arguments (Pointer,F32,U32). The earlier M3f
DLL rejects it801/null. M3g loads all three in one native module and executes them.

Four input forms (raw PTX, genuine plain/compressed nvFatbin, compressed alternative
profiles) times two entry/order arrangements times six sizes1,63,64,65,257,50000
times three kernels yield144 cases. For alternative profiles, the upper image also
changes add to sub, proving the selected program rather than only its loadability.
Every output starts as NaN, with64 guards. CPU add/sub/fill is the independent oracle.

| Check | Actual result |
| --- | --- |
| Multi-entry execution | 144 cases,1,210,800 outputs and9,216 guards passed |
| Repeated lookup | Different function tokens for the same entry executed correctly |
| Same names in separate modules | Different add/sub behavior remained isolated; unloading one left the other usable |
| Function/module lifetime | All entry handles invalid after module unload; foreign context rejected400; context destruction invalidated handles |
| Missing entry / missing arguments |500/null and INVALID_VALUE respectively |
| Invalid later entries | Duplicate entry, missing final delimiter and unsupported later instruction rejected218/801/null; context recovery passed |
| Module entry cap |32 entries loaded/resolved, last entry launched;33-entry parser input rejected |
| Repeated kernel |100 cases,6,500 outputs and6,400 guards; separate from144 cases |
| Load/unload stress |1,000 three-kernel module cycles passed; all final function handles invalid |
| Resource fault injection | Partial creation and destruction helper failures preserved live handles and avoided double destruction |
| Rust / Python |44 workspace tests including prepared ignored GPU/producer checks and19 Python tests passed |
| Lint |Workspace/all-target Clippy with warnings denied and rustfmt passed |
| Native ABI/regressions |12 structures matched all C/Rust offsets/size/alignment; M1~M3f actual GPU and official upstream sample/CLI regressions passed |

The failure injections exercise pure native-resource bookkeeping callbacks, not
an actual device-loss/driver failure.1000 cycles are a bounded stability check,
not a production lifetime guarantee. Additional duplicate/isolation/recovery
launches are excluded from the144-case totals.

## Independent application connection

A separate synthetic C executable, built with pinned official CUDA12.0.107 headers,
imports normal nvcuda.dll symbols and contains no CT loading code. One genuine
compressed fatbin supplies all three entries. The host queries four handles
(including a duplicate), launches the mixed ABIs, checks1028 outputs/256 guards,
and checks stale-handle rejection after unload. Both app-local staging and public
ct.py run passed with executable/asset bytes preserved.

- Measured executable SHA-256: `0384ead55c0aac4c512b65b9e32e044f24b823fd688f12b67cc86ffc54bbaac8`.
- Compressed three-entry fatbin SHA-256: `35f1955e4b008eee581c6c88728fab389686171b82eb65dc3f077bca365cf138`.

This consumer is synthetic, not an unchanged third-party application. Fresh rebuild
hashes may differ. NVIDIA headers emitted two anonymous-struct extension warnings;
CT source compiled and the executable passed. Vendor packages/binaries/generated
inputs/raw logs stay ignored. Only CT code, synthetic source fixtures and harness/docs
are published; pinned producer provenance follows [M3d](M3d-RESULTS.md).

## Reproduce and limitations

Acquire pinned prerequisites as in [M3d](M3d-RESULTS.md#reproduce). Preserve an M3f
DLL/hash in ignored .cache/m3g-baseline before changing that source; on a new clone,
build8b73a53 separately without resetting another checkout. The native baseline
comparison checks that hash before execution.

```powershell
$env:CARGO_INCREMENTAL = '0'
./scripts/run_m3g_smoke.ps1
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py'
python scripts/check_compatibility_profile.py
cargo clippy --workspace --all-targets -- -D warnings
```

The GPU matrix/lifetimes/stress and independent app path were verified separately;
`-ApplicationOnly` exercises just the new C consumer after the matrix has passed.
SPIR-V Tools validator was unavailable on PATH and its check is skipped.
NVIDIA execution/coexistence and AMD remain unverified. Native Intel compilation is a separate check.
This does not implement P03 multidimensional launch, P04 stored globals/device calls,
Runtime/cudart, shared/warp semantics or general CUDA compatibility.

## Review

A fresh-context whole-branch review found no actionable findings in production
code, synthetic/native harnesses, docs or manifest. It independently passed the
default Rust suite,19 Python tests and manifest validation. The reviewer did not
rerun native stress/application execution, actual driver failure or official
SPIR-V validation. Native results above are the implementation session's runs.
