# R2f: actual export-query calls and error propagation

## Result

An explicitly labelled diagnostic callback confirmed two actual cuGetExportTable calls by official Runtime12.9.79. With the same CT provider and fixed version-presentation samples, the early query returned801 and Runtime continued to real cuInit(0), which returned0. The post-init query then returned801; Runtime returned801/count−1 without an observed device-count call.

| Surface | Sample | Actual sequence | Runtime |
| --- | --- | --- | --- |
| Original missing export |12000,12090 | Actual version801/output0; labelled version presentation; real init0 |36/count−1 |
| Explicit v2-only rejection |12000,12090 | Early export query801; actual version801/output0; labelled presentation; real init0; post-init export query801 |801/count−1 |

This establishes the public dispatch/error boundary in the observed prefix. It does not decode any private table, prove that returning a table is sufficient for subsequent startup, or qualify Runtime/app support. The production Driver version remains801/output0. No successful table, count or NVIDIA identity was fabricated.

The actual requested opaque16-byte identifiers, in order, were:

1. `f8cff95121468b4eb9e2fb469e7c0dd9`, before the version/init calls.
2. `6bd5fb6c5bf4e74a8987d93912fd9df9`, after real init0.

The first rejection did not prevent initialization in these samples. The second rejection propagated as the returned failure. These are path-specific observations, not decoded semantic table names or general dependency claims.

## Intervention boundary

The separate ExportRejectObserver first calls/logs the actual5arg CT resolver. Only cuGetExportTable/version3000/flags0 with actual result0/null pointer and optional status absent or1 may be presented as result0/diagnostic callback, with status1-to0 explicitly labelled when supplied. No raw GetProcAddress export is added, and the old4arg resolver still returns500/null. Native controls verified both preservation rules and resolver self-selection.

The public-signature callback clears valid output storage and returns1 for null arguments without reading UUID storage. With valid arguments it reads exactly16 bytes, accepts only the two observed identifiers for logging, and returns801. Unexpected identifiers/preconditions or callback exceptions invalidate and stop the child. Rejection is a distinct diagnostic event, not a kernel guard. Original/presented resolution and actual rejection events remain distinguishable in the trace.

The base v2 callback, added wrapper and export callback stay strongly referenced through restored IATs and explicit Runtime unload. Guard/failure-blocked callbacks also clear valid output storage before returning999. Original guarded-worker behavior remains the default of the new optional worker hooks.

## Verification

Thirteen fresh isolated children passed their finite expected-result gates: the original eight R2d controls, an extended native contract child, two rejection samples and final faithful/nominal controls. All arms used the same fresh CT binary and pinned Runtime where applicable. Final controls matched their original counterparts. Ordinary direct Driver initialization/count still passed with one Intel device; no application kernel was launched. Normal arms had zero guard hits and callback failures, verified IAT restoration and Runtime unload.

The original20 native guard checks passed and were repeated within the extended31-check child, which adds11 export/resolver/null/output checks. Official-header compilation verifies PFN_cuGetExportTable_v3000 and the16-byte CUuuid. Eight focused Python tests for the new diagnostic and13 existing bootstrap tests passed. The clean private checkpoint also passed the full CPU11/11 lane: Python310, Rust209 with4 existing ignored tests, Runtime129, formatting, Clippy, profiles/registry and publication checks.

Independent read-only design and implementation review completed. Findings about hidden guard rows, boolean status acceptance and blocked-callback output clearing were reproduced with failing tests and corrected. An additional query-before-presentation ordering test was also added and passed after correction. Final review reported no remaining blocker to this bounded experiment; it did not independently execute the native capture.

## Provenance

- Source fingerprint: `2e03b2bb279fb830f6efb8eb5a86598adc662aa359f2f2c87ed5bdd9a38488a1`.
- Private clean checkpoint commit: `6b5865d80d5405ab455c89546997f6a324827ef7`; tree: `8943e635c5f2ae4ac149936f1065218736c0d819`.
- Local capture ID: `0e6deacc9bdc40ceb571c3f9d3fd97a7`.
- Original-eight capture SHA256: `8be258230ebf32c0f32cbdb707ffeb17244492ea42c32b0f974b0089dc57d60f`.
- Extension capture SHA256: `d176f670e445f8a0dd65355b8ace47629552f60c1b71fbb7e662f18536a560e9`.
- Saved extension recheck SHA256: `16ee68e287fa1627a8a046dc851b458cb4fbc0423981f166354e5a08feb33b8c`.
- Fresh CT DLL SHA256: `99cc224f60ec0499803986f778474e0335d098768c49a5bfeddd7fe8c2baebc1`.
- Runtime DLL SHA256: `760c38928bbe5759f7b31ed6692599eb7ec83cedd5702e84c2b72028a89837e1`.

Saved recheck validates local scope/order/source/artifact/observation consistency; it is not another native execution or external attestation. Vendor bytes, compiler environments, DLLs and raw captures remain ignored local artifacts. No staging, root commit, upload or installation was performed. Root production Rust/Cargo/include bytes, protected files, HEAD/index and privacy checks are recorded separately in the local final verification.

## Reproduce and next work

From the repository root, run `python scripts/run_export_rejection.py --python <isolated-python> --archive <pinned-runtime-archive>`. Recheck the resulting local folder with `python scripts/run_export_rejection.py --recheck <capture-folder>`. This is a Windows x64 diagnostic and requires the existing authenticated compiler/SDK setup.

The next investigation is a documented contract for the post-init opaque table, using identifiable public evidence and independently checked signatures/layouts before implementing any successful return. Discovering an identifier does not supply its ABI. Keep unknown tables explicitly unsupported; do not guess table contents or promote the diagnostic version presentation into a shipping version. Runtime enumeration, useful application execution, same-GPU performance evidence and Intel release qualification remain open; AMD follows the Intel milestone.
