# R2c synthetic bootstrap experiment

The isolated protocol experiment identifies the next attempted call on a fixed test surface: with successful sample version responses12000/12090, the pinned Runtime calls `cuInit(0)`; the test-only peer rejects it801. Responses801/output0, success/output0 and success/11000 stop with Runtime35 before any observed init call. **This is synthetic evidence, not CT initialization, a supported Driver version or a CUDA application success.**

## Fixed experiment and observations

A standalone Rust test DLL has exactly five CUDA exports and two test-only exports. It has no CT/backend linkage and no device-count, memory, copy, module, stream or kernel entrypoints. Init always rejects; the public-signature export-table query returns801/null. No private table or callable private pointer is fabricated. The only mode-dependent behavior is the configured version-query response. The response is configured once before the first lookup/call.

The same official Runtime12.9.79 DLL is used in five traced/untraced pairs. Observation starts before Runtime DLL loading and ends after the device-count prefix, so this experiment does not attribute every record specifically to DLL loading versus the explicit API call.

| Synthetic version response | Actual calls recorded on this fixture | Runtime result |
|---|---|---|
|801 /0 | export-table query801 → version query801 |35; count−1 |
|success /0 | export-table query801 → version query0 |35; count−1 |
|success /11000 | export-table query801 → version query0 |35; count−1 |
|success /12000 | export-table query801 → version query0 → cuInit(0)801 |801; count−1 |
|success /12090 | export-table query801 → version query0 → cuInit(0)801 |801; count−1 |

All tracing-off results match their corresponding tracing-on results. No case reports device-count success. The opaque table identifier is recorded as raw16-byte hex `f8cff95121468b4eb9e2fb469e7c0dd9`; no undocumented table-content meaning or necessity is inferred from this value. In this fixture prefix, rejecting that table query did not prevent the later init attempt in the12000/12090 arms. It could still matter on later paths.

Separate real CT nominal/observed before-and-after controls remain unchanged: Driver version801/output0, Runtime35/count−1, no observed cuInit. A direct native fixture contract child passes19 argument/configuration/address/ABI checks; the standalone Rust peer has4 passing tests. The official-header compile-only assertions verify the primitive functions, both resolvers, public export-table query signature,16-byte UUID and112-byte trace-row layout.

**Confound:** the peer exposes fewer functions than real CT's41 successfully resolved pointers. The comparison with CT is not a pure version-only intervention. Only comparisons between peer modes isolate sample-response behavior on this fixed fixture surface. The observed init attempt is a concrete next investigation point, not proof of CT's complete mandatory initialization bundle or a truthful numeric version.

## Provenance and safety boundary

All children use isolated no-site Python startup and process-local DLL bundles. Source, interpreter, peer/provider, SDK/ABI artifacts and copied DLL hashes are checked before each child; loaded module paths/hashes are checked inside the child. Exact exports/imports are inspected before first execution; alternate/dotted forwarding targets, extra launch exports and GPU/CT dependencies are rejected. Export parsing permits only same-name local debug annotations.512-row overflow, native faults, unexpected success, relabelled nominal/observed traces and manufactured initialization/table success are rejected.

This is15 children: four real CT controls, ten synthetic pair members and one direct fixture-contract child. The runner never launches an application kernel. It does not install a driver, change machine settings or execute a test-supplied PTX program. The root production Rust implementation remains unchanged. Saved recheck is local input/observation integrity validation, not a new execution or authenticated attestation.

Frozen source fingerprint: `563c37b6ed31bc071db396d423357808a98380a66009ffb7eecee41b9b4697de`. Private source checkpoint: `c1d56ec71895d0b65a68348fc7d6db90f24bb84b`, tree `0c810941d6e707b00a3e58ed7f7435c09bd4615b`. Only ordinary reporting/plan edits followed that snapshot; product fingerprint is unchanged.

Final local capture: `e46d9544cd1248649896473f0c51a6f4`; SHA256 `5046a9d71a93eb258b35911b91265765eae4135c462bcc02149c7f8fae40c619`. Saved recheck SHA256: `9ecf4942520c9be850bc30ac54139daffab1aedc63805f1d8decae8fba64fa27`. Peer DLL SHA256: `aceaa4c746e92299570a671c9dc68e2361c093ccbe72dc58719d622d6985f144`; real CT control DLL SHA256: `2574bdfe87cc98fb9e714b4c29f5b2db8dedd41b0134e321cbce2a920c95d6a0`. The peer and real CT are different binaries with different roles; neither identity may substitute for the other.

The clean source checkpoint passed CPU11/11, including Python289, Rust209 with4 existing ignored tests, Runtime129, formatting, Clippy, profiles/registry and publication checks. Standalone peer Rust4, direct native fixture19 and all15 child expectations passed separately. The clean-source cache setup correction was retested in a source copy with no preexisting cache. Root product files, protected11, original HEAD/index and publication privacy checks are verified in the local acceptance record. Raw snapshots, SDK packages, compiler environments, disassembly and local paths stay ignored; no vendor bytes or raw logs are uploaded.

## Reproduce

Prerequisites are the existing verified MSVC host/producer environment and private Python3.14 interpreter described in the [R2b recipe](R2B-BOOTSTRAP-RESOLVER-RESULTS.md), Rust/rustc, and the official Runtime archive whose SHA256 is `179e9c43b0735ffe67207b3da556eb5a0c50f3047961882b7657d3b822d34ef8`.

```powershell
python scripts/run_bootstrap_peer.py --python .cache/r2-apps/cupy-env/Scripts/python.exe --archive .cache/r2b-runtime-12.9/runtime.zip
python scripts/run_bootstrap_peer.py --recheck .cache/bootstrap-peer-runs/<run-id>
```

This test DLL must never be used as a product bundle. The normal CT/CuPy qualification commands do not select it, and its synthetic results use a separate schema/classifier. The peer's compile-time surface cannot submit GPU work even when a sample version query succeeds.

## Reference review and next work

NVIDIA documents [minor-version compatibility within a CUDA major family](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html); that does not give CT a supported version merely from its header/request ceiling. A primary-source check of [ZLUDA driver implementation at08b19b2](https://github.com/vosen/ZLUDA/blob/08b19b28b7c334936846b3aeb61a43aef053e9a1/zluda/src/impl/driver.rs#L598) shows both an export-table dispatch layer and a version result based on that project's API constant. Those implementation choices are reference material, not CT conformance evidence; no ZLUDA code was copied and no advantage/comparison-performance claim is made.

Independent design and final read-only reviews found no material issue in this bounded experiment and required the synthetic-versus-CT distinction above. A first inventory run stopped before child execution because local debug-symbol annotations were mistaken for forwarders; a red/green regression corrected that parser. A clean-source Python run exposed a missing test-cache-directory setup; it was fixed and revalidated from a fresh source copy.

The next [real-provider counterfactual plan](superpowers/plans/2026-10-29-r2d-real-bootstrap-candidate.md) preserves CT's actual lookup surface and init/device-count behavior while isolating any version-response intervention. Only after that evidence should an actual startup bundle and compatibility-profile/version contract be considered. Product version support, CuPy GPU execution, complete CUDA functionality, performance, second Intel PC and AMD remain unqualified.
