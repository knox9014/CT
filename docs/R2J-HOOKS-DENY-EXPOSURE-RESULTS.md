# R2j: both-table exposure reaches private context denial

## Result

The official pinned Runtime12.9.79 reached actual CT Driver enumeration inside its startup path after both authenticated deny-only tables were presented. Both diagnostic version samples,12000 and12090, followed the fixed sequence:

1. Reject the early optional export query801; observe actual CT version801/output0 and separately label the diagnostic version presentation.
2. Actual `cuInit(0)` returns0.
3. Present the104-byte CUDART deny table and56-byte hooks deny table for their exact reviewed UUIDs/order.
4. Actual `cuDeviceGetCount` returns0/count1; actual `cuDeviceGet(ordinal0)` returns0/device0.
5. CUDART private context slot2 enters its typed deny callback, clears its context output and returns801. Only the context bit is set (mask2).
6. Runtime returns3 with the caller's count still−1. The private denial therefore does not propagate as Runtime801.

This is the finite denial branch predicted before execution by pinned Runtime disassembly: initialization15cb0 calls the private context function before the hooks getters; a denial returns its initialized error3. It does not establish an Intel device fault, successful Runtime enumeration or application support. Production Driver version behavior remains801/output0. No shipping version is authorized by these diagnostic presentations.

## Boundaries and implementation

The new observer, worker, checker and runner are separate diagnostic infrastructure. Production Rust/Cargo/include bytes are unchanged. The additional public `cuDeviceGet` callback uses the typed CUdevice-pointer/int signature; a compile-only official-header check verifies it against `PFN_cuDeviceGet_v2000`. Private layouts remain reference-derived contracts, not official public ABI guarantees.

The child authenticates a fresh standalone fixture capture, copied/loaded DLL and source/artifact identities. Before exposure it checks image bounds, alignment,56-byte hooks metadata, zero holes and in-image callable addresses, in addition to the existing104-byte CUDART checks. Only the exact third UUID query in the reviewed phase can receive the hooks pointer. All fixture callbacks remain typed denials; no hooks buffers or context service are provided.

Expected state is precisely mask0/stopped0 before exposure and mask2/stopped1 at prefix restoration and after Runtime unload, with reserved0 throughout. Other masks, wrong phases, guard/callback failures or subsequent blocked wrapped calls invalidate the experiment. The latch is monotonic and has no reset export. It identifies the context entry, not its invocation count, and is not a complete native-call sandbox.

Runtime is restored and unloaded before final fixture state is read; the fixture is then freed and module absence checked without further fixture calls or memory reads. Both unload checks passed. The direct version/context controls after Runtime teardown remain intentional controls outside the observed startup prefix. No wrapped calls were blocked, no public guards fired and no callback failures occurred. Hook getter bits remained clear throughout.

## Validation

- Fresh prerequisite fixture: Rust3 tests and C++47 direct checks passed.
- Fresh bootstrap pipeline: prior17 children plus two new exposure samples and two final controls, totaling21. Original controls remained identical; new samples matched only the predeclared Runtime3/count−1, Driver count1/device0, private mask2 branch.
- Saved source/artifact/observation recheck passed. This is local consistency verification, not another native run or external attestation.
- Five focused Python tests cover layout bounds/holes, exact query presentation, expected versus unexpected private latch states, finite result/order gates, and full metadata mutations including missing fixture identity, blocked calls and failed unload.
- Clean private checkpoint CPU11/11 passed: Python329, Rust209 with4 existing ignored tests, Runtime129, formatting, Clippy, registry/profiles and publication checks.
- Independent read-only implementation/runner review found no native-execution blocker; the reviewer independently ran the five focused tests. The recorded ABI command is informational; the explicit executed command uses the authenticated compiler/headers and the resulting object is hashed.

## Provenance

- Source fingerprint: `bd2386f6549fed42a94e0f3a1a2fb3d7f19364be03890b785d36ca5a8e54eedf`.
- Private clean checkpoint commit: `aac03e6819b491aaaa8a02b41cd2fa684cff61cb`; tree: `eae42f17707714e8825c1de55407b54637aa920a`.
- Local bootstrap capture ID: `08bec75a6ca54723bc617c359e6e1f1e`.
- Hooks exposure capture SHA256: `db4d7f96f23787b3523bbd10b32ac7b656a96b95ba2d35b0b7f7ad8a34ac51a1`.
- Saved recheck SHA256: `0cf0ba981e5b087d7ff2686ecdcfd2e0deca4b4d4b443919fcca77bfc7c543e6`.
- Fresh CT DLL SHA256: `d7215c116199bed35cb109c2ff47225865535009ca751d30417d356c9d9fa7e5`.
- Fresh fixture DLL SHA256: `c7f67a7a93b231a17d79fc10acd4ecc1472f4ce714c834cbcbfb8ce5614c8053`.
- Fixture capture SHA256: `9f72ac292e1abc8a2696c617ce9ad1c9cf83791debe066486f17dd02437af0a0`.
- Pinned Runtime DLL SHA256: `760c38928bbe5759f7b31ed6692599eb7ec83cedd5702e84c2b72028a89837e1`.

Raw captures, SDKs, binaries and absolute paths remain ignored local artifacts. Final local verification scanned662 public-source files with0 privacy findings, confirmed104 production files unchanged against R2i and all11 protected files unchanged, and confirmed root HEAD/index preservation. Only this report and the plan changed after the clean checkpoint; the execution source fingerprint remains identical. Independent saved-evidence review confirmed the report and CPU counts. No staging, root commit, upload, installation or accepted-worktree edit was performed.

## Reproduction and next boundary

Run `python scripts/run_hooks_exposure.py` with the pinned local setup. Explicit `--python`, `--archive` and `--source-root` overrides are supported. `--recheck <local-bootstrap-capture-folder>` validates saved consistency.

The next implementation question is CUDART slot2's inactive primary-context semantics, ownership and lifetime. Its pointer signature alone is insufficient to substitute the existing public retain operation; the pinned reference includes an inactive-context requirement. Establish that contract and teardown/state tests before providing a real context service. Hooks getter/buffer semantics remain unimplemented and were not reached. Useful CUDA application execution and Intel release qualification remain open.
