# R2e bootstrap dispatch investigation

**Goal:** Distinguish a missing public export selecting Runtime's error36 fallback from an actual CT initialization failure. Keep production code and the Driver version response unchanged.

**Method:** Use the exact pinned Runtime12.9.79 DLL and R2d CT DLL. Regenerate local disassembly and correlate the public symbol lookup, fallback assignment, post-init query and error propagation. A separate process may read the known in-image pointer slot after the already bounded Runtime call, before unloading. It must not invoke that pointer or modify memory, lookup responses, callbacks or opaque table contents. Store only relative target RVAs in observations.

- [x] Verify39 relevant instructions against freshly generated disassembly; read the symbol string from the pinned PE image and correlate both R2d missing-export observations.
- [x] Run an explicit diagnostic worker copy with only an after-call slot observation. Retain the original isolated startup, guard latches, restored IAT, callback lifetime and explicit unload. Fail closed on image/hash drift or an out-of-image observation target.
- [x] Capture nominal/faithful before/after controls, deliberate guard contracts, ordinary direct Driver and the two fixed presentation samples. Preserve original validation by validating the original result separately from the explicitly labelled slot observation. Bind source, generated-worker, provider, Runtime and observation hashes. Stop on any unreviewed result or fault.
- [x] Record static versus dynamic evidence, current tests and privacy checks. No new claim of application support or shipping version authorization.

The independent read-only reviewer could not start because of a usage limit; it supplied no review finding or approval. This phase introduces no additional callback/export surface intervention. A later experiment supplying a public export callback or any private table requires separate design review; no such intervention is included here.

## Next experimental boundary

If the fallback pointer is observed, the next candidate is a separate public-signature cuGetExportTable rejection callback that clears valid output storage, logs the opaque16-byte identifier, and returns801. This tests dispatch and error propagation only. It must never return success with invented table contents or authorize a shipping numeric version. Actual table layout/semantics and supported startup contract remain unresolved.

## Outcome

Both samples observed the internal36 fallback in the cuGetExportTable dispatch slot after the bounded call. Eight children and13 focused regression tests passed their expected diagnostic gates. See `docs/R2E-BOOTSTRAP-DISPATCH-RESULTS.md`. No new callback/export intervention or application execution was performed.
