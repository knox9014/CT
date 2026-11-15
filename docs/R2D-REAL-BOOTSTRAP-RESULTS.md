# R2d: real CT bootstrap experiment

## Result

The real CT Driver initialized successfully and directly enumerated one Intel(R) Arc(TM) B390 GPU. The pinned official CUDA Runtime12.9.79 did not complete device enumeration. This is a completed diagnostic experiment, not application compatibility or a shipping CUDA version claim.

| Arm | Actual CT behavior | Runtime result |
| --- | --- | --- |
| Nominal, before/after | Driver version801/output0; no observed init |35/count−1 |
| Faithful guarded observation, before/after | Same actual version response; no observed init |35/count−1 |
| Diagnostic presentation12000 | Actual version801/output0; separate intervention0/12000; actual cuInit(0)0 |36/count−1; no observed count call |
| Diagnostic presentation12090 | Actual version801/output0; separate intervention0/12090; actual cuInit(0)0 |36/count−1; no observed count call |
| Separate ordinary Driver control | cuInit(0)0; cuDeviceGetCount0/count1; current context null | No Runtime loaded |

Production cuDriverGetVersion remains801/output0 before and after the experiment. Both finite presentation samples reached actual initialization and then the same Runtime error. A numeric response alone is insufficient for this observed startup prefix. The specific missing API, table or other condition has not been identified.

The official error name for36 is cudaErrorCallRequiresNewerDriver ([NVIDIA Runtime types](https://docs.nvidia.com/cuda/archive/12.9.0/cuda-runtime-api/group__CUDART__TYPES.html)). That name does not establish that updating the physical Intel driver fixes this CT path, nor identify a required private table.

## Contracts and validation

Eight fresh isolated children ran in a fixed order: nominal, faithful, deliberate guard contract, ordinary direct Driver, sample12000, sample12090, faithful, nominal. Before/after controls matched. Same-provider identity checks cover copied and loaded DLLs, both resolver ABIs, source/interpreter hashes and the authenticated SDK archive.

The separate native contract child passed20 checks, including six deliberate module-load/kernel-launch guard hits through raw lookup and both resolvers. Guards return801 without dereferencing image/function/stream/argument pointers; the module guard clears valid output storage. Normal Runtime arms had zero guard hits and zero callback failures. Actual invalid-argument and initialization ordering was retained: count before init returns3, invalid init flags return1, null count after successful init returns1. No device count was substituted.

Default-faithful observer hooks are separate from the labelled intervention subclass. Pointer identity is verified before wrapping; callback failures latch and invalidate the result. Unexpected Runtime statuses other than the reviewed negative36 branch stop execution; regression tests reject35,801 and999 in that branch. Independent read-only review found this status gate issue, and verified the correction.

IAT slots were restored and verified. Callback references remained live while the owned Runtime DLL was explicitly unloaded, and module absence was checked before child exit. Prefix and teardown observations are distinct. This is not a claim that every internal allocation was observed or that all Driver calls were traced. Export inventory gates cover the existing code-loading/submission routes; no application kernel was launched.

The clean private source checkpoint passed CPU11/11, including Python302, Rust209 with4 existing ignored tests, Runtime129, formatting, Clippy, registry/profile and publication checks. The20 native checks and eight diagnostic children are separate from those CPU totals. Production Rust/Cargo/include bytes remain unchanged relative to R2c.

## Evidence identity

- Product-source fingerprint: `43691ebeb44ab906badd5ea6c7a2481286678e44e8db842902060267ae395d51`.
- Private checkpoint commit: `186fd9e051b63333394f05b92f777328ca08b76a`; tree: `6e1273ad4e8d9b3566651427dfa59601eed6f9f5`.
- Final local capture: `30d8c264d37743d0a959de18c3d3167e`; capture SHA256: `7b2cfeb7e760a7112951bc4c8690e60699f4474e9b44a2a07e79ceaef6e3a36d`.
- Saved recheck SHA256: `5685550303bee48af3609c5f2a9b7c8ff41dcfa9377efa16cede84273cb11022`.
- CT DLL SHA256: `94118900fa757c9a81ee8d97b60a8e118a5f9c2731911ea277e8db7d11e5748b`.
- Official Runtime DLL SHA256: `760c38928bbe5759f7b31ed6692599eb7ec83cedd5702e84c2b72028a89837e1`.

Saved recheck validates local observation/artifact consistency; it is not a fresh execution or third-party attestation. SDK bytes, DLLs, raw logs, environment details and checkpoints remain in ignored local storage. No publication was performed. The private final verification record tracks current privacy/protected-file/index checks separately.

## Next boundary

Trace the condition producing Runtime36 after actual initialization and before an observed device-count call. Begin with read-only mapping and existing lookup evidence. Any additional callback/export surface intervention needs an independently reviewed, separate experiment with unchanged controls. Do not implement guessed private table contents or choose a shipping Driver-version integer to bypass the error.

The minimum actual startup bundle, truthful compatibility-profile/version contract, Runtime enumeration, useful application execution and Intel release qualification remain open. AMD follows the Intel milestone.
