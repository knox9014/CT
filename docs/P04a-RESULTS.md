# P04a stored scalar globals: implementation progress

Tasks1-5 are implemented. Task6 has actual Intel native diagnostic execution.
Authenticated evidence auditors and Task7's four new required gates, clean candidate
recapture and independent artifact audit remain pending. This is **not completed
P04a qualification**. The previous C44-pass result concerns its older pinned code.

## Implemented

Bounded mutable scalar `.global .align 4 .u32` supports zero/explicit initial bits,
ordinary/volatile direct reads and writes, and shared module storage without hidden
user arguments. Candidate identity includes stored values and known-unsupported
names/classes. Driver39 adds GetGlobal with nullable outputs and distinct module
memory access/free/query semantics. Native module destruction owns global cleanup;
uncertain failures retain resources and poison the context. Runtime22 freezes
bindings at End and verifies version1/flags0/size4 symbols through the same pinned
Driver before lookup/launch. Other sizes/version2 remain unsupported.

## Executed checks

Local suites passed:132 root Rust tests,61 standalone Runtime tests,110 Python
tests, root/standalone fmt and clippy, original-header Driver39 and Runtime22 typed
ABI probes. Pinned SPIRV-Tools accepted four new translations and rejected two
corrupt controls; the older validator controls passed too. These are not48 gates.

The actual new nvcc shared-cudart host was rebuilt with default device-runtime:
the primary command contains no `--cudadevrt=none`. Two fresh positive seeds checked
100 ordered updates,17 output values,64 guards on each side and preserved input
arrays against the independent Python oracle. Eight diagnostic modes passed:
two positives, a numerical no-op whose GetGlobal path was forwarded before launch
suppression, missing/foreign GetGlobal returning35 with valid memory roundtrips,
old no-variable nvcc vector executables working through both providers, and an
actual-used u64 rejected with801. Direct Driver checks additionally passed100
ordered calls, two-context/module isolation, unload/reload reset and1000 tiny
module lifecycles. This is not a reliability or performance claim.

Earlier diagnostics used `--cudadevrt=none`; those did not meet the default-runtime
requirement. A reviewed command-contract test failed on that recipe, then passed
after correction. All eight modes above were freshly rebuilt and rerun afterward.

| Diagnostic artifact | SHA256 |
| --- | --- |
| nvcc host EXE | d579fd7dd673ca68810aadb462516979a367902e20956d27ddb01bee60c6fea9 |
| CT Driver | db6dc52c404646ad662156e5df74fb8546fc38a91dc3664ef3c9fe2eae2b71d4 |
| CT Runtime | 402394a16b384a19921bac1e7e823258cf294cf87221cbf80da4fbaaf49e4a72 |

Diagnostic source fingerprint:
`f8d768291164397c096bb37b38a1c8061f64cd2bf41be7c233f9b4a24f0312bd`.
It matched live sources after execution. Ignored diagnostic manifest SHA256:
`df1d6d6b46f2676b9333ee56d34aa340607a8f678cd74bec9921033874ac98e2`.
This ran in the feature checkout preserving11 preexisting user files; it is not a
clean-checkout acceptance identity. Vendor files, private paths and raw logs remain
ignored locally. Reproduce with `python scripts/run_p04a_smoke.py` and the existing
authenticated local diagnostic producer plus real Intel stack. The MSVC override
remains diagnostic; supported-host, AMD, NVIDIA, framework and release are unproven.

## Rejection migration and independent review

Historical `default_used_global.cu` is unchanged and is not relabeled a positive.
Current C negative source/EXE/PTX roles explicitly use the separate
`default_unsupported_global.cu`, which actually reads volatile u64 and expects801.
The new positive is `tests/fixtures/p04a/global_runtime.cu` with its own expectation.

One fresh-context independent review checked the implemented compiler, ownership,
Driver, Runtime and diagnostic sources. Its two P2 findings were fixed in one
RED-to-GREEN pass: native missing-name mapping, including first/second query and
failed cleanup, and the default-runtime positive recipe. No minor was deferred.
This source review excludes the pending artifact audit and independent native run.

## Rulings

1. Reuse the feature checkout with exact staging and11 preserved user hashes;
   reserve the existing managed clean checkout for acceptance. Use an ignored
   PowerShell ledger instead of unavailable Bash helpers. Cost: manual bookkeeping;
   current diagnostics do not replace clean acceptance.
2. Commit IR/emitter together to keep accepted IR executable. Private emission
   returns Result for inconsistent global tables; public translate already did.
   Cost: private consumers propagate errors.
3. Arc removed unused Linkage-only globals. Emit the official Level Zero host-access
   extension alongside Linkage, as recorded in [preflight](P04a-PREFLIGHT.md).
   Cost: this SPIR-V lowering requires Intel support; AMD needs its own lowering.
   No dummy reads or hidden user arguments are introduced.
4. Numeric one-past may be another live global base. Test the boundary past all
   live globals and reject spans crossing one extent. Cost: raw addresses carry no
   provenance/generation guarantee, matching the existing allocation policy.
5. Absolute nvcc keep directories failed under the workspace path containing
   spaces; relative keep paths worked. Cost: commands require the recorded cwd.
6. Map INVALID_GLOBAL_NAME to unsupported only in native global query. Preserve
   other native errors and cleanup retention. Cost: unavailable storage returns801
   rather than999 so callers can use the unsupported fallback.

General global types/arrays/constants/externs, address-taking, device linking,
symbol-copy APIs, concurrent global writes/atomics and arbitrary CUDA/AI workloads
remain outside this slice. Task6 authenticated reconstruction and Task7's full48
required gates are still unfinished; no future pass count is projected.
