# R2n: official Runtime invokes the native primary callback

## Verified diagnostic prefix

Official pinned Runtime12.9.79 invoked the successful native primary-context callback through an authenticated diagnostic CUDART table. Both explicitly labelled version-presentation samples12000/12090 followed the same finite sequence: early optional query801, actual CT version801/output0 then labelled presentation, actual init0, CUDART/hooks table pointers, actual count0/value1 and DeviceGet0/device0, private context callback0/non-null handle, then the controlled cuDeviceGetName(length256,device0) stop801.

Runtime returned3/count−1 as predicted by the fixed static branch. This is a successful private context prefix, not successful Runtime enumeration or an application run. The name query was deliberately not forwarded. No hooks getter, module/launch operation or other private denial callback ran. No production version or shipping compatibility claim changed.

The diagnostic Rust provider links the public CUDA functions and private callback into the same rlib global Runtime. Its new104-byte static table reuses typed deny slots except slot2. The provider has46 existing CUDA exports and4 diagnostic exports; the production DLL still has its original46. Table storage and callable addresses are checked inside the authenticated loaded provider image. The provider remains loaded through Runtime restoration, Runtime unload, state queries and public cleanup, then until process exit. It is not independently unloaded like the earlier standalone table fixture.

## Foreign loader regression and correction

Two initial captures were correctly rejected and remain failures: b4bb733002f1497fac35710cc44d24de and b9b021393a1947f6b0767ef9c1285379. The latter recorded the cause: a foreign-module Windows FlsGetValue lookup during private callback execution, when telemetry was calls1/result0/non-null0. The old generic lookup guard checked CUDA state before discriminating the module. Final callback telemetry1/0/1 did not make those failed captures valid; actual IAT restoration succeeded, while the failure latch caused the reported restoration ValueError.

The fix discriminates the module before the CUDA gate. Foreign Windows lookups use their original loader function and are recorded separately. Same-provider CUDA lookups retain strict native-state and boundary gates. A causal regression test proves a foreign in-flight lookup forwards while the same-provider lookup is still rejected. The successful new capture records the same FlsGetValue intermediate state without treating it as completed CUDA callback evidence. Final prefix/result/native state requirements remain unchanged.

This is not a complete native-call sandbox. After the planned stop, subsequent observed CUDA-provider forwarding invalidates the child; unrelated Windows loader activity remains functional.

## Lifecycle evidence

Deny masks stayed0 before exposure, at prefix restoration and after Runtime unload. Native telemetry was0/0/0 initially and exactly1/0/1 at prefix restoration and after Runtime unload. Runtime unload and IAT restoration checks passed, with no guard/callback failures or blocked CUDA forwarding in accepted samples.

After Runtime unload, public primary GetState returned0/flags0/active0; public reset returned0; GetState again returned0/flags0/active0 and current context was null. These prove the reported public outcomes and cleanup return, not the cardinality of private ownership maps or an external driver leak audit. Separate R2m native tests provide direct tracked-map cleanup evidence; it is not substituted for unobserved state in this experiment.

## Validation and provenance

- Fresh original production controls8 plus diagnostic provider children8 passed. The latter comprise C++47 deny-table checks, direct enumeration, before/after faithful/nominal controls and two context-prefix samples. Bridge before/after controls matched; direct observations matched the production provider.
- Five focused Python tests passed, including finite trace/results, callback states, reset outcomes, guard/teardown metadata and the foreign-versus-provider lookup regression. Independent review repeated focused tests and checked static branch/lifetimes before native execution.
- Clean private checkpoint CPU11/11 passed: Python334, Rust215 with6 existing/opt-in ignored tests, Runtime129, formatting, Clippy, profiles/registry and publication checks. No ignored native testcase was implicitly run by this CPU lane.
- Saved source/artifact/observation consistency recheck passed; it is not a second native run or external attestation.

Source fingerprint: `05b394e42c79b7d50db7a0ae35b7c69bf1e9b8cab283d3675a83f06d2bde949e`. Private checkpoint commit: `b0a26e8526b2fc88dc7cac1f5cb500fe1af22064`; tree: `e36f40fd276b8e9af4c3fabc4ddce1bc8f49f169`.

Local accepted capture: `e565983a42cd4aee9e12d411dad91cad`. Context capture SHA256: `6b2ddeed4fde095727e5ad7d56a832e54313ceb1e6f011cfe8c97aebafb45978`. Diagnostic provider SHA256: `a7da1c8dcd10c628d37b20a837af317a103c1e6890e3e38168da58d0d4aaa995`.

Raw SDKs, binaries, commands/absolute paths and logs remain ignored local artifacts. Final local verification checks product/protected files, privacy and root HEAD/index. Production Rust/Cargo/include bytes remain unchanged from R2m; new implementation here is diagnostic fixture/scripts/tests. No staging, root commit, upload, install or managed-worktree edits were performed.

## Reproduce and continue

Run `python scripts/run_primary_runtime.py` with the pinned local setup, or `--recheck <local-bootstrap-capture-folder>` for saved consistency. Explicit --python/--archive overrides are supported. The pipeline stops before the next child on any unexpected result.

The next bridge step can forward the real name query and address the following public total-memory/attribute queries under a separately fixed guard. Implement a truthful total-memory query from device-reported metadata before extending the prefix; do not invent capacity, hooks buffers or compatibility versions to force success. Useful CUDA application execution remains open.
