# P09a2-C: default device-runtime registration results

Verified 2026-10-23 on Windows x64 / Intel Arc B390.
Native-tested code candidate: `258bf92dd9ba13b2d4ff630ddb40b095ac96041c`.
Execution-scope SHA256:
`97a0be2a1f2d7f34a6a7074f0228eff718095358e007e7f9fa5608a8f8287b15`.
The fixed candidate passed all44 clean required gates, errors=[], clean=true,
release_claim=false. Documentation-only heads do not replace this tested identity.
Independent read-only final reconstruction returned errors=[] and confirmed the
same live commit/fingerprint, empty Git status and44 passed cases with no skipped
or unavailable cases. No release or general CUDA compatibility claim.

## Implemented boundary

The standalone Rust Runtime adds RegisterVar for22 entries. The producer keeps
shared cudart and non-RDC PTX8.0/sm52 while removing cudadevrt=none. It does not
support default static cudart, device-runtime function execution, globals storage
or cross-module linking.

Version2 registration owns its raw primary image and a bounded flat dependency
list.32 dependency slots plus null,33 unique images,16MiB/image and64MiB aggregate
owned data limit CPU snapshots. Pointer aliases deduplicate only within a token;
there is no recursive wrapper traversal. Empty/kind2-only containers can pass
structural inspection without becoming executable. Strict PTX extraction remains
unchanged. Active leases and native ownership retain their whole byte charge.

Variable callbacks copy both names and flags/size metadata, with256/token and2048
live mappings. Host identities are opaque, no declared-size allocation occurs.
Unknown/retired tokens reject payloads first; failed tokens preserve their first
error; concurrent retirement cannot restore a live registration.

Any version2 registration or registration containing any variable metadata returns801
before Driver initialization, context selection or native load. This conservatively
also rejects an otherwise supported kernel with an unused global in the same token.
A separate no-variable version1 token remains usable. No vendor symbol exception
or unimplemented successful execution is introduced.

## Validation evidence

- Root workspace116 Rust tests and nested Runtime55 tests passed; fmt/clippy passed.
- Python105 tests passed, including artifact/command/qualification tamper checks.
- Original vendor RegisterVar declaration, independent CT declaration and actual
  Rust DLL typed calls passed, including64-bit size,22 exports, missing/forwarded
  Driver controls and pre-Driver801. Existing14 ABI and21-kernel subset remain.
- Authenticated default-link producer prepare/replay passed. CPU observer records
  v1/v2 constructors, one machine-code-only dependency,33 function callbacks and11
  variables. It deliberately fails allocation and proves no GPU execution.
- Actual Arc native9 modes and independent fresh-seed replay passed: six genuine
  compiler-stub positive scenarios, a used volatile-global negative, a supplementary
  typed zero-additional-Driver-call/Arc sibling/retire control and no-op launch numeric negative.
  Positives independently check17 outputs, four guards and both21-element inputs.
- Actual EXE, Runtime DLL and fatbin mutations were each rejected; originals restored.
- All41 previous required gate IDs remain, with three additions:
  producer.default_device_runtime, arc.runtime_default_abi, arc.runtime_default.
  The fixed candidate passed all44 required cases with no skips or unavailable
  cases. The earlier pre-review acceptance is superseded.

## Implementation rulings

- Reuse the feature checkout and managed clean acceptance worktree; preserve11
  original user-file hashes and stage explicit paths only. The ignored PowerShell
  ledger replaces unavailable Bash helpers; this needs manual bookkeeping.
- Version2 with a null dependency-list pointer now returns invalid1 under C;
  version3 remains unsupported801. This updates the former blanket v2 rejection.
- Use PowerShell7 (pwsh), as existing evidence scripts require utf8NoBOM;
  Windows PowerShell5 cannot run that existing encoding recipe.
- The CPU-only observer uses independent observed ABI types, keeping vendor API
  declaration proof in the separate official/CT/Rust native gate. No vendor header
  is edited. The observer is not ABI or execution evidence.
- Dlink artifact names follow the output executable prefix, not the source prefix.
  Bind exact default_dlink/host_dlink/negative_dlink outputs in their recipes.
- The used-global EXE receives the same explicit Runtime-import opt-in as the
  genuine positive EXE; static-cudart and unknown imports remain rejected.

## Limits and follow-up

Current compiler/SDK evidence is diagnostic on the existing unsupported host,
using authenticated NVIDIA/STL bytes and a local installed-host hash snapshot.
No separately reviewed supported-host pin exists. AMD/NVIDIA execution, frameworks,
full globals/constants, symbol-address/copy APIs, device-function resolution,
dynamic parallelism and general CUDA/device-runtime compatibility remain unverified.
Vendor binaries/headers, raw logs, constructor dumps and machine paths stay ignored.

## Independent review and fixes

The whole-C reviewer found no product ownership/state/eligibility defect. Its P2
producer replay finding was fixed: capture/replay now executes the observer in a
fresh isolated directory, compares fresh rows and all three raw images, then rehashes
original artifacts. Regression tests first observed a missing fresh-execution request;
fresh output/raw forgery tests now fail closed, and actual observer replay passed.

The P3 unused-variable control finding was promoted to important because the spec
requires an otherwise executable kernel. A regression first showed its generic symbol
absent from actual oracle PTX. The control now uses ct_oracle_add and the same allocated
device arguments as its runnable sibling; both blocked paths assert zero additional
Driver calls, then the sibling executes on Arc. A separate actual Rust ABI probe also
proves blocked registration preflight without Driver initialization. Fresh native9-mode
capture and independent replay passed after the fix. No minor finding was deferred.

The code reviewer initially declined to certify the then-running clean result.
The fixed clean run subsequently passed44 gates; its separate independent artifact
reconstruction also passed without source/artifact/HEAD mutations. It also excluded
release/qualified-host/other-GPU/framework claims, arbitrary unreadable pointers and
full linking/global storage; these remain unverified rather than inferred from C.

Publication scans passed and all11 original user-file hashes were preserved.
The feature remains an existing draft PR; no merge or release was performed.
