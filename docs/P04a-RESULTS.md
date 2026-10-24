# P04a stored scalar globals: verified Arc preview

2026-10-24: all seven bounded P04a implementation/verification tasks are complete.
The fixed candidate passed **48/48 required combined cases** in the existing clean
validation checkout:0 failed,0 skipped,0 not-run. Independent read-only artifact
reconstruction returned errors=[] and confirmed188 result/referenced artifact hashes
unchanged before/after audit, together with unchanged HEAD, clean state and live
source fingerprint. No merge or release is claimed.

This is the bounded Windows x64/Intel Arc preview, using the explicitly diagnostic
MSVC override. It does not qualify a supported host toolchain, AMD/NVIDIA execution,
arbitrary CUDA applications, static cudart, device-runtime functions or AI frameworks.

## Exact native-tested identity

- Code commit: `1a2e7e1e77691ad451c6d33ecee3c1efb5c6f141`.
- Live source fingerprint: `dd34131a2620fb4b7d84bb8de6c092d19a679642a501e852c20f8b306d77de11`.
- Source clean:true; release_claim:false.
- Observed GPU: Intel(R) Arc(TM) B390 GPU.
- Report SHA256: `b63088202d7cd53868820af40bec22b9f86e4c87b940e98522d3e3b165cc68a2`.
- Configuration SHA256: `d93391a6d306717d57219167faa84a58c545a82b0370a28f13e97493a97a8da4`.
- Toolchain file SHA256: `dcf614230dfee457bea5e8851b05ab28e35fce09cf2b8c34affc2b074a3f8e96`.

| Final clean artifact | SHA256 |
| --- | --- |
| nvcc host EXE | e12b1c5716d00d5bd37911a51c1fafffa26e8fc32c350bd9d92289993d0da055 |
| CT Driver | 6d53a07f4987736d3fbddb9b088807f78967ba98f58e883041eb211952a51ccf |
| CT Runtime | 6bbaa61551688756cca1174cd7f7363619132f2fd77443ef51b0a8f71574d814 |
| Global ABI manifest | 098a32ef7d8942f6f5631b0394882952f36fbb2362f808b4ac1e25b5d7826942 |
| Global Runtime/Driver manifest | 1dbbe2ee6255aab4510d35df084c5b956dd4ca7f13b3b453241f77064e4569a6 |

The result document may have later documentation-only commits; the commit above is
exactly the code actually exercised. Local reports reside under
`results/local/p04a-clean-1a2e7e1/` in the managed validation checkout. Vendor
binaries/headers, absolute local paths and raw logs remain ignored and unpublished.
The11 original user files in the main checkout were preserved and excluded from staging.

## Implemented contract

Mutable scalar `.global .align 4 .u32` supports optional visibility, zero/explicit
initial bits and direct ordinary/volatile reads/writes. The module owns shared
storage across entries, without hidden user arguments;256 declarations maximum.
Candidate identity includes stored initializers and known-unsupported names/classes.

Driver39 adds `cuModuleGetGlobal_v2`: nullable outputs, bounded names, context/module
checks and output reset. Copies/fills/pointer arguments accept a live exact global
extent, while free returns1 and allocation-metadata queries return801 without writes.
Native module destruction owns globals. Query/teardown failures preserve uncertain
ownership and poison unsafe contexts; globals never reach native memory free.

Runtime22 freezes bindings at End and verifies version1/flags0/size4 symbols through
the same owned/pinned Driver before lookup/launch. Missing/unsupported/mismatched
bindings are sticky and retain the module for retirement. Other sizes/version2
remain unsupported. No Runtime symbol-copy API or general linking is implied.

## Executed verification

The final required lane retained every existing44 ID and added exactly
`validator.global_u32`, `arc.global_abi`, `arc.runtime_global`, `arc.global_driver`.
Cases include rejection controls as well as successful workloads;48 is not a count
of independently supported CUDA applications.

The lane passed root Rust132 tests, standalone Runtime61 tests and Python125 tests,
plus fmt/clippy, pinned original-header Driver39/Runtime22 ABI and real SPIRV-Tools
positive/negative controls. The final combined Rust run passed135 tests with its
ignored native/producer tests enabled. Actual native execution, exact tool/input
binding and fresh replay are required; a child exit-zero/status JSON is insufficient.

A genuine nvcc shared-cudart host was rebuilt with default device-runtime settings:
the primary recipe contains no `--cudadevrt=none`. Its unchanged EXE/fatbin ran
through CT for two fresh positive seeds. Independent Python expectations checked
100 ordered updates,17 output values per update,64 guards on each side and full
input preservation. Eight native modes passed: two positives; numerical no-op with
GetGlobal forwarded before launch suppression; missing/foreign GetGlobal returning35
with memory roundtrips; existing no-variable nvcc vector EXEs through both providers;
and an actual-used u64 rejected with801. Both default-runtime dlink fatbins are
required compiler outputs, alongside the primary PTX/fatbin/stub snapshots.

Direct Driver checks passed100 ordered calls, two-context and same-named-module
isolation, unload/reload reset and1000 tiny module lifecycles. Driver raw output is
an assertion-completed100/1000/2 summary, not a retained per-cycle trace; the fixed
consumer asserts observations during fresh native replay. This is not a reliability,
performance, concurrency or other-hardware claim.

Auditors reconstruct closed schemas, live source/inputs, authenticated producers,
compiler/Rust recipes, original header pins, exact bundle roles and raw observations.
Replays use isolated copies and fresh seeds, followed by rehashing original inputs.
ABI evidence also binds the Driver DLL to retained Cargo output and the producer's
cl/link/vcvars identity. Tamper tests reject substituted EXE/DLL/PTX/readbacks,
rehashing a compatible foreign ABI DLL, changed recipes/compiler identity, source
changes, extra/missing fields, stale pointers and forged successful child output.

## Independent review and superseded observations

One fresh-context product review found two P2 issues, fixed in one RED-to-GREEN pass:
operation-specific native missing-name mapping and the default-runtime positive recipe.
An earlier `--cudadevrt=none` diagnostic was not sufficient for the default requirement.
The historical `default_used_global.cu` remains unchanged and is not relabeled a positive.
Current C negative source/EXE/PTX roles use the separate actual-used volatile u64
`default_unsupported_global.cu`; the new positive is `p04a/global_runtime.cu`.

Independent artifact review found one P2: the ABI DLL was only checked against its
own declared hash. A reproducing test accepted a rehashed compatible foreign DLL;
the fix now compares retained Cargo output and binds the actual compiler/recipe.
During that same fix pass, a clean rerun reached47/48: the wrapper passed an absolute
producer path to a legacy relative-path CLI, causing duplicated header paths. A
command-contract regression failed first, then passed with the relative argument;
actual ABI replay and Python125 tests passed. A new full clean run then reached48/48,
and only that final candidate was accepted. Prior incomplete/failed runs were not
promoted. No minor finding is deferred.

The final independent audit reconstructed completed artifacts read-only, without a
source re-review or another native run. Native fresh execution/replay occurred during
the required lane; AMD, NVIDIA, supported-host, framework and release remain excluded.

## Rulings and their costs

1. Reuse the feature checkout with exact staging and11 preserved user hashes, and
   the existing managed clean checkout for acceptance. Keep an ignored PowerShell
   execution ledger instead of unavailable Bash helpers. Cost: manual bookkeeping
   and retained local evidence caches; neither is published.
2. Commit IR/emitter together to keep accepted IR executable. Private emission
   returns Result for inconsistent global tables; public translate already did.
   Cost: private consumers propagate errors.
3. Arc removed unused Linkage-only globals. Emit the official Level Zero host-access
   extension alongside Linkage, as recorded in [preflight](P04a-PREFLIGHT.md).
   Cost: this SPIR-V lowering requires Intel support; AMD needs its own lowering.
   No dummy reads or hidden user arguments are introduced.
4. Numeric one-past may be another live global base. Test beyond all live globals
   and reject spans crossing one extent. Cost: raw addresses carry no provenance or
   generation guarantee, matching the existing allocation policy.
5. Absolute nvcc keep paths failed under the workspace path containing spaces;
   relative keep paths worked. Legacy Runtime ABI producer arguments likewise must
   be root-relative. Cost: these commands require the recorded working directory.
6. Map INVALID_GLOBAL_NAME to unsupported only for native global query. Preserve
   other native errors and cleanup retention. Cost: unavailable storage returns801
   rather than999 so callers can use an unsupported fallback.
7. A/C producers were freshly regenerated in the managed checkout. Their exact
   source/recipe/observer inputs were unchanged by subsequent ABI-only fixes, so
   those fresh immutable artifacts were reused and revalidated/replayed by the final
   lane. Cost: no second compilation of unchanged producer inputs; all P04 fixtures
   and ABI probes were rebuilt for the final candidate.
8. Use an optional explicit CompilerDirectory for the new ABI gate; preserve default
   behavior of existing callers. Bind cl/link/vcvars and Cargo output independently.
   Cost: this verifies the recorded diagnostic compiler, not official host support.
9. Keep the compiler-output role set closed, including default dlink images.
   Cost: changed future compiler outputs need an explicit recipe update.

General global types/arrays/constants/externs, address-taking, device linking,
symbol-copy APIs, concurrent global-write/atomic semantics and arbitrary CUDA/AI
workloads remain outside this slice. The overall universal CUDA translator is ongoing.
