# R2b static Runtime bootstrap contract plan

> **For agentic workers:** Use superpowers:executing-plans after the contract evidence below is established. This is planned work, not an implementation pass.

**Goal:** Turn the observed CuPy bootstrap failure into a justified shared feature bundle before changing CT's version reporting.

**Architecture:** Keep the pinned CuPy wheel and64-value workload unchanged. Audit the embedded Runtime's bootstrap requests and official Driver semantics, construct small native contract probes, then decide which minimum truthful compatibility surface CT can implement. Existing R2 diagnostic stays fail-closed while behavior changes; update its accepted stage only after reviewing the new outcome.

**Tech stack:** Existing Windows x64 Python/Rust/official CUDA header toolchain; process-local Driver bundles.

**Spec:** `docs/R2-CUPY-BOOTSTRAP-RESULTS.md` and the R2 gate in `2026-10-27-intel-qualification-next.md`.

## Constraints

- No arbitrary version increase, false NVIDIA device identity or kernel-specific special case.
- Resolver request ceilings, Driver compatibility version, Runtime build version and virtual compute target are different values. A requested symbol version alone does not identify the embedded Runtime build.
- Keep nominal distributed binary execution separate from pointer-wrapping diagnostics and synthetic native probes.
- The existing448 trace rows contain optional requests; do not convert the308 null successes or96 unsupported resolutions into mandatory API counts.
- Raw observations, tools and vendor bytes remain ignored. Preserve protected11/root index/HEAD; no root staging, publication or device-driver installation.

## Tasks and acceptance

- [x] Inspect the exact release's Runtime build/version query and wheel metadata to establish the embedded Runtime version without initializing a GPU. Execute a version query only after its source proves it cannot advance to launch. Bind this evidence to the wheel hash.
- [x] Review official `cuDriverGetVersion` semantics and both resolver ABIs against pinned headers/documentation. Write argument/output/error/version contracts and identify which truthful compatibility-version meaning CT can offer. Do not use the current resolver ceiling12000 as the answer by assumption.
- [x] Classify observed requests by symbol/version/flags and correlate actual calls separately. Add minimal native probes using the same relevant official Runtime generation to isolate bootstrap contracts; a probe is diagnostic evidence, not an upstream application result. Preserve missing/null/error controls.
- [ ] Specify the smallest common initialization bundle: version reporting and any proven mandatory device/context/resolver prerequisites. For each member, list official ABI, supported semantics, error behavior, limits, tests and excluded modes. Leave optional graph/peer/texture/etc features out unless actually required. If opaque/proprietary initialization contracts appear, document the boundary instead of fabricating tables.
- [ ] Review the contract independently. Only then write failing implementation tests, implement the justified bundle in Rust, run native header ABI checks and existing regression gates, and rerun the unchanged CuPy workload under a newly reviewed safety gate. Preserve the next blocker or independently verified output. Never classify an expected diagnostic failure as application support.

## Completion boundary

R2 completes when the selected application, workload, original execution path, first blocker, independent oracle, controls and required common bundle are all explicit. R3 then implements that bundle. CuPy array smoke success alone will still leave a meaningful end-user workload, second Intel PC, numerical/performance qualification and AMD work outstanding.

## 2026-10-29 evidence and ruling

CuPy's statically linked Runtime query returns12090; `_getLocalRuntimeVersion` is a different, dynamically loaded Runtime path and was not used. This establishes12.9, not its exact patch build. An authenticated official12.9.79 dynamic Runtime comparator reproduces the same448-row bootstrap trace and the same failed Driver version call; it is not proof of identical static-library bytes.

No successful numeric Driver version is currently justified. Leave801/output0 in place. Independently reviewed, per-symbol resolver corrections are possible without that claim: four audited bootstrap names gain the safe no-PTDS-variant fallback and verified request ceiling. This is a separately bounded correction, not completion of the common initialization bundle. See `2026-10-29-r2b-bootstrap-resolvers.md` and `docs/R2B-BOOTSTRAP-RESOLVER-RESULTS.md`.

## 2026-11-06 startup dependency audit

Both saved CuPy 14.2.0 traces from the current Driver replay match their recorded SHA-256 hashes. Each makes the same v2 requests below with flags 0. The execution column separates calls seen in CuPy from calls seen in the official Runtime 12.9.79 experiments.

| Driver request | CuPy resolver result | Execution evidence |
| --- | --- | --- |
| `cuDriverGetVersion` (2020) | Success with pointer | CuPy calls it and receives 801 with output 0. Runtime reports 35. |
| `cuInit` (2000) | Success with pointer | The official Runtime calls it successfully after diagnostic version presentation. |
| `cuGetExportTable` (3000) | Success with null pointer | After successful init, the official Runtime's unresolved dispatch returns 36 before device count. The subsequent table-pointer experiment exposes additional opaque dependencies. |
| `cuDeviceGetCount` (2000) | Success with pointer | Direct Driver control enumerates the Intel device. The early official Runtime experiment stops before an observed count call. |
| `cuDevicePrimaryCtxRetain` (7000), `cuDeviceGetName` (2000), `cuDeviceTotalMem` (3020), `cuDeviceGetAttribute` (2000) | Success with pointer for each | Later guarded official Runtime experiments reach the context and metadata sequence. Under the explicit software target, the observed sequence ends at attribute 17. |

Sources are the [unchanged CuPy replay](../../R2-CUPY-BOOTSTRAP-RESULTS.md), the [Runtime dispatch observation](../../R2E-BOOTSTRAP-DISPATCH-RESULTS.md), the [table-pointer experiment](../../R2I-CUDART-TABLE-EXPOSURE-RESULTS.md), and the [Runtime topology result](../../R2V-RUNTIME-TOPOLOGY-RESULTS.md).

The candidate common bundle has two separate gates. The first is a supported version contract and a justified post-init export-table contract. The second is the context and device-metadata sequence reached under the guarded experiment. The exact opaque table behavior and a truthful value for attribute 17 on CT's Windows submission path are still unresolved. A successful lookup establishes pointer availability. Require a call and its outcome before classifying a request as an application dependency. Keep the unchanged CuPy device-count replay as the acceptance gate before advancing to its workload.
