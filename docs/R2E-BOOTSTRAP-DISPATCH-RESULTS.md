# R2e: locating the Runtime36 dispatch boundary

## Finding

The pinned official Runtime12.9.79 has an internal error36 fallback for unresolved Driver functions. In both fixed version-presentation samples, its cuGetExportTable dispatch slot was observed pointing to that fallback after cudaGetDeviceCount returned36. The current CT resolver returns success with a null pointer for this requested, unsupported public symbol; no cuGetExportTable implementation was called.

This narrows the next investigation from a generic version failure to a concrete public dispatch boundary. It does not establish the contents or implementation contract of the opaque tables requested beyond that boundary. The CT initialization itself still succeeds, and ordinary direct Driver enumeration still returns one Intel device. No application or Runtime enumeration succeeded in this experiment.

## Static evidence and limits

Fresh disassembly of the hash-pinned Runtime was checked against39 instruction assertions. The symbol string at RVA65c20 is cuGetExportTable, requested with public version3000. Failure or a null resolution selects fallback RVA14db0 and stores it in dispatch slot RVA83078. The fallback returns hexadecimal24, decimal36.

After a successful initialization call, the startup routine calls that slot at RVA230b0 with the opaque identifier stored at RVA63a60. Its nonzero result is propagated and cached as the startup failure before the device-count path proceeds. The earlier optional query at RVA2301b is a different call site and uses a different identifier; accepting or ignoring that earlier query would not establish that later startup requirements are met.

The post-init opaque identifier bytes are `6bd5fb6c5bf4e74a8987d93912fd9df9`. This is an observed identifier, not a decoded layout or semantic name. Static control flow and an after-call pointer snapshot support the explanation; there was no instruction-level breakpoint trace of the indirect call. No table contents were supplied or dereferenced by the diagnostic addition.

## Fresh bounded execution

An explicitly diagnostic copy of the R2d worker adds only a read of the pointer slot after the existing bounded Runtime call and before DLL teardown. It checks the exact Runtime hash, in-image slot bounds and an in-image target, then records a relative RVA. It never invokes the read target, writes that slot, supplies new exports or creates new callbacks. The original worker and production code are unchanged.

Eight isolated children repeated nominal/faithful before controls, deliberate guard contracts, ordinary direct Driver control, both fixed samples and faithful/nominal after controls. All original R2d gates passed after separating the explicitly labelled pointer observation from the original result. Both samples returned36/count−1 with actual init0 and no observed count call; their slot targets were RVA14db0. Before/after controls matched, and those Runtime arms also retained the fallback slot. Normal arms had zero guard hits/callback failures, restored IATs and verified Runtime unload. The separate contract child passed20 checks. Existing focused regression tests passed13/13 again.

The independent read-only reviewer failed to start because of a usage limit and supplied no review. This result must not be described as independently reviewed. A new public-callback or private-table intervention remains a separate review boundary.

## Evidence identity

- Unchanged product-source fingerprint: `43691ebeb44ab906badd5ea6c7a2481286678e44e8db842902060267ae395d51`.
- Runtime DLL SHA256: `760c38928bbe5759f7b31ed6692599eb7ec83cedd5702e84c2b72028a89837e1`.
- Existing CT DLL SHA256: `94118900fa757c9a81ee8d97b60a8e118a5f9c2731911ea277e8db7d11e5748b`.
- Local evidence folder ID: `6b40677a78a64bb697378594ec800ae8`.
- Static analysis SHA256: `7702c014763cc844d96e1c9ba7d0656a5ec516aa7adb0154502665187ebace9e`.
- Diagnostic worker SHA256: `c42bd7f47d2ae2ffd48bf8bdb2177e90527aabb6c239a447bff815e7ddbb2be9`.
- Fresh capture SHA256: `a90be9efe7852a9b47895c6af5978124e7ef091b7b3435f4fc2c61e74e82e396`.

Vendor disassembly, diagnostic worker, raw output, absolute paths and DLLs remain ignored local artifacts. Saved consistency recheck is not another native execution or external attestation. No upload, root commit or staging was performed. Prior full CPU11/11 results apply to the same unchanged product-source fingerprint; this phase reran the13 focused tests, not the full CPU lane.

## Next step

Review a separate experiment that supplies only the public cuGetExportTable signature, logs the16-byte identifier, clears valid output storage and returns801. Compare it against the unchanged missing-export surface while keeping guards and both fixed samples. Its purpose is to observe actual calls and error propagation, not to claim that rejecting a required table completes Runtime support.

A successful private table requires known contracts, validation and a truthful supported profile. Do not fabricate a successful table, bypass the error or advertise a shipping CUDA version. Useful application execution and Intel qualification remain open.
