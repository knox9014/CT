# Stored Scalar u32 Globals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Main-agent inline implementation and one independent whole-branch review remain selected. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** P04a: execute unchanged genuine nvcc programs using stored scalar u32 globals through Runtime22, the same Driver39 and Intel Arc.

**Architecture:** Common typed global IR lowers to native exported CrossWorkgroup storage. The backend's module owns symbol memory; Driver classifies its ranges separately from user allocations. Runtime freezes variable bindings at End and validates names/sizes against the same Driver before launch.

**Tech Stack:** Rust/std, SPIR-V1.0/OpenCL1.2 validator, original Level Zero/CUDA declarations, existing diagnostic nvcc12 and Windows x64/Arc evidence tools.

**Spec:** [stored-global design](../specs/2026-10-24-stored-global-u32-design.md).

Status: all seven bounded P04a tasks completed. Final clean candidate1a2e7e1 passed48/48 required cases and independent artifact reconstruction. See [verified results](../../P04a-RESULTS.md); this is diagnostic Arc preview, not a release or universal CUDA claim.

## Global Constraints

- Only mutable scalar `.global .align 4 .u32` with optional `.visible` and initializer; zero default. Direct symbol load/store and volatile variants only.256 total declarations,128-character names,4 bytes/scalar and1024 stored bytes/module.
- Preserve unused legacy global declarations as known-unsupported lookup metadata; no arrays/constants/extern/weak/device functions/address expressions/linking. All lookup-visible candidate identity must agree.
- No hidden entry arguments or new user parameter ABI. Driver39 adds only GetGlobal_v2; Runtime remains22. Constructors stay CPU-only and retain first-failure/retire policies.
- Native module owns globals; no zeMemFree/global cuMemFree. Separate range classifications; live-global memory queries801, user allocation behavior unchanged. Explicit failure retention/no blind retry.
- Preserve existing limits,44 gate IDs, app-local same-Driver path,11 original user files, exact staging/publication scans. No supported-host/AMD/NVIDIA/framework/release claim.

## Review Focus

1. Known-unsupported versus absent symbols must not change lookup801/500 with fatbin candidate selection: Task1 identity tests.
2. A partial query/unload failure must never free global storage separately or expose an unusable pointer: Task3/4 fault tests.
3. An unchanged user entry signature must stay unchanged when globals are emitted: Task2 validator and Task6 real host-stub tests.
4. Unregister during first metadata validation must not lose names/size/late module ownership: Task5 deterministic barrier tests.
5. C's historical u32 rejection must not masquerade as an unchanged positive application: Task6 explicit source-role migration and new positive/negative oracles.

### Task1: Stored/unsupported global IR and lookup identity

**Files:** `crates/ct-ptx/src/{lib,parser}.rs`, its module/memory tests; `crates/ct-codegen-spirv/src/lib.rs`, `crates/ct-cuda/src/images.rs`, related image tests/profile docs.
**Interfaces:** `GlobalStorage::{MutableU32{initializer:u32},Unsupported}` and `Global{name:String,storage:GlobalStorage}` deriving equality. Module/Kernel share `Arc<[Global]>`, so legacy single-kernel parse retains module data. Add `Value::Global(String)` for direct memory addresses and `volatile:bool` to Load/Store (false for old forms). Compiled/CompiledModule retain shared descriptors; existing public parameter lists remain user arguments only.

- [x] Add `stored_global_u32_profile`, `global_volatile_address_forms`, `legacy_global_metadata_stays_unsupported`, `candidate_lookup_identity_is_observable`: initializer zero/7/signed-bit edges,256/257 names, duplicates/entry collisions, optional visibility without consuming the next entry prefix, direct read/write, unsupported symbol offsets/address-taking/types. Candidate tests accept reordered same descriptors; reject initializer/type/class/name differences and unsupported-versus-absent, while irrelevant details within Unsupported remain unobservable.
- [x] Run affected PTX/image tests and observe unsupported/missing fields before implementation.
- [x] Implement the spec's exact grammar and typed IR, with checked initializer parsing and existing code budgets. Propagate globals through parse/translate wrappers; compare normalized lookup metadata before any native work. Never accept used legacy symbols or silently drop volatile.
- [x] Run PTX and Driver image suites, workspace fmt/clippy; verify old instruction/global rejection boundaries. Commit exact paths.

### Task2: Native global SPIR-V with unchanged user argument ABI

**Files:** `crates/ct-codegen-spirv/src/{lib,emit}.rs`, codegen tests; create `scripts/check_global_spirv.py`, `tests/test_global_spirv.py`.
**Interfaces:** Keep private `generate_module(kernels:&[Kernel])->Vec<u8>` reading their shared global table; generate(k) retains its Kernel globals. Emit one native variable per stored descriptor and a separate name->id table that survives per-kernel register resets. Compiled global metadata travels alongside SPIR-V.

- [x] Add failing tests `global_storage_shared_across_entries`, `global_does_not_add_parameters`, `global_volatile_memory_operands`: check stored initializers, Linkage Export, module scope, exact old user-argument count/order, and volatile mask3/alignment4 versus ordinary mask2/alignment4. Old no-global output/signatures remain valid. Reject inconsistent manually supplied module global tables before emission.
- [x] Implement CrossWorkgroup u32 OpVariable, constant initialization, Linkage capability/decorations and direct Global-address resolution. Preserve existing register-pointer handling and no-contraction policy. No native host-access vendor extension is required for the selected Linkage path.
- [x] `check_global_spirv.py --validator PATH --lock PATH` builds real CT translation fixtures and invokes authenticated spirv-val with existing opencl1.2 target. An exit-zero fake validator or missing tool cannot count as valid. Native feasibility sources remain supplementary, not product translation evidence.
- [x] Run codegen tests, actual validator, old validator gate and affected fmt/clippy. Commit exact paths.

### Task3: Backend symbol ownership and partial-failure retention

**Files:** `crates/ct-backend-intel/src/{lib,modules,fault_tests}.rs`, `crates/ct-level-zero/src/{abi,loader}.rs` as needed; original-header ABI probe and tests.
**Interfaces:** `NativeGlobal{pointer:u64,size:usize}`; Module owns bounded named metadata and pure `global(&self,name:&str)->Option<NativeGlobal>`. Add `Backend::load_module_entries_with_globals(&self,c:&mut Context,spirv:&[u8],entries:&[&str],globals:&[(&str,usize)])->NativeResult<Module>`; old load methods delegate with empty globals. No new crate dependencies/root Cargo edits.

- [x] Add fake API tests for exact original zeModuleGetGlobalPointer ABI, expected names/size4, null/unaligned/overlapping pointers, missing optional symbol, failure at each query, cleanup failure and module destroy. Assert no per-global zeMemFree and no native work for no-global modules beyond old behavior.
- [x] Reserve owned names/kernel/global records before native create. Resolve native global API only when needed; query every stored name after creation, retain module handle before fallible native calls, reject pointer/size disagreement. Missing optional API is unsupported; query errors use existing operation-specific native mapping. Explicit unload clears metadata only after successful module destroy; failures retain handles and poison as current policy.
- [x] Verify actual original header signature with the pinned header and a typed native call. Run backend fault suite, Level Zero ABI gate and root clippy. Commit exact paths.

### Task4: Driver39 GetGlobal and module-owned range operations

**Files:** `crates/ct-cuda/src/{lib,modules,memory_queries,entrypoints}.rs`; create `device_ranges.rs`; update Driver header/DEF/profile/ABI tests and native consumer.
**Interfaces:** `unsafe extern "system" fn cuModuleGetGlobal_v2(out:*mut u64,size:*mut usize,module:*mut c_void,name:*const c_char)->i32`. Canonical GetProc name cuModuleGetGlobal maps floor3020..12000 after original typedef proof; exactly39 entries. Shared pure range helpers classify live current-context user/global extents without merging ownership.

- [x] Add tests `global_query_nullable_outputs_and_errors`, `global_copy_free_and_query_are_distinct`, `global_range_lifetime_and_context`, `global_query_poison_never_exposes_pointer`: size-only/address-only success, both-null1, missing500/known-unsupported801, invalid handle400, context precedence, bounded name, outputs reset. Copies/fills/pointer arguments accept exact4-byte global ranges; free returns1 without native free; live-global memory queries801 without writes. User ranges preserve old behavior; reject cross-context/one-past/stale ranges and overlap.
- [x] Load module with stored descriptor names/sizes; retain legacy lookup names separately. Reuse backend module metadata as the authoritative range owner. Apply the new range predicate to all synchronous copy/fill/launch validation sites; retain ordinary allocation bases for free/context destruction. Native query disagreement prevents module publication and follows existing rollback/retention.
- [x] Independently compile original CUDA12 typedef/header and CT declarations, call actual Rust DLL with64-bit pointer/size outputs and nullable cases. Only after proof update Driver header/DEF/profile/resolver to39. Old38 ABI remains a verified subset; update hardcoded parity explicitly, not by deleting assertions.
- [x] Run Driver/core/ABI tests and native GetGlobal/copy/free/query consumer on Arc. Commit exact paths.

### Task5: Immutable Runtime bindings and same-Driver global extension

**Files:** `crates/ct-cudart/src/{registration,registration_variables,kernel_driver,kernels,driver,lib}.rs`, registration/kernel/state tests and Runtime profile behavior text. Public exports stay22.
**Interfaces:** RegistrationData freezes `OnceLock<Vec<Variable>>` at successful End under the registry lock, before marking Ready. Record keeps live variable-count accounting after the move. Leases/native cache retain RegistrationData through retire. Add `KernelDriver::prepare_globals()->Result<(),i32>` and `global(module:usize,name:&[u8])->Result<(u64,usize),i32>`; prepare returns Runtime-domain35, global uses Driver errors. Old five-symbol kernel extension remains separate.

- [x] Add RED tests `u32_bindings_live_through_unregister`, `unregister_during_global_validation_owns_late_handle`, `global_validation_failure_keeps_module_owned`, `missing_global_extension_does_not_poison_old_paths`. Cover repeated End, failed/post-End/retired precedence, binding budgets released once, allocation failures before native work, ordinary/two contexts and first-use sharing. Use barriers, no timing sleeps.
- [x] Permit only version1 metadata where every variable has flags0/size4; version2/other sizes remain pre-Driver801. Resolve GetGlobal from the same pinned DLL only for these modules. Publish native module ownership before verifying every registered symbol/size; verify before function lookup/launch. Missing/unsupported/mismatch -> sticky module801; retain handle for explicit retire/drain. Preserve function-scoped errors and callback CPU-only behavior. No new Runtime symbol-copy APIs or backend linkage.
- [x] Native typed missing/forwarded global provider returns35 while memory and no-variable launches still work. Verify22 ABI remains exact. Run full nested tests/fmt/clippy plus existing Runtime gates. Commit exact paths.

### Task6: Genuine CUDA globals, direct Driver consumer and rejection migration

**Files:** Create `tests/fixtures/p04a/global_runtime.cu`, guarded Driver fixture/consumer, supported-unused-u32 control and `p04a_noop_driver.c`; new ABI/Driver/Runtime smoke/evidence scripts/tests. Update C negative role to new `tests/fixtures/p09a2/default_unsupported_global.cu`, C smoke/checker input bindings; preserve historical default_used_global.cu unchanged.
**Interfaces:** New auditors use existing `audit_manifest(path,root,*,execute=False)->list[str]`, closed schemas, source/producer/command/import/module/DLL hashes and latest-pointer roles. No-op Driver proxy forwards GetGlobal39 correctly before suppressing launch, so a missing extension is not mistaken for a numerical no-op rejection.

- [x] Add independent oracle tests before scripts. Genuine Runtime source emits full guarded readbacks only; Python owns expected init/updates. Validate unchanged generated EXE/fatbin and actual symbol/volatile PTX. Cover zero/nonzero init, supported unused sibling global, two entries,100 ordered calls,17 outputs with64 guards and preserved inputs. No concurrent global-write/atomic claim.
- [x] Direct Driver consumer loads two same-named globals/modules, uses nullable GetGlobal outputs and copies, proves mutation isolation, two-context isolation, unload/reload reset and1000 tiny module lifecycles. Fault tests cover resource failures separately; stress count is not reliability parity.
- [x] A new actual-used u64/unsupported fixture preserves the current C negative801 contract. Source/EXE/PTX roles must explicitly point to that new input; old rejection source is not relabeled a successful unchanged program. New P04 positive has its own source/hash and correct host expectation.
- [x] Run positive actual Arc paths, no-op numerical negative, wrong/missing global controls and fresh-seed independent replay. Mutate EXE/DLL/global descriptors/readbacks and require rejection. Rehash originals and record source/qualification exactly. Commit CT-owned source/evidence only.

### Task7: Required gates, fixed clean acceptance and publication

**Files:** `scripts/run_validation.py`, runner tests, coverage/profile catalogs, result/support docs; existing draft PR.

- [x] Add failing tests retaining all44 old IDs and introducing exactly validator.global_u32, arc.global_abi, arc.global_driver, arc.runtime_global, with exact tools/commands/input roles. Cover stale pointers, forged child success, source/config tamper, capture-time fresh execution and later independent reconstruction.
- [x] Integrate closed-schema evidence and keep diagnostic/qualified distinction. Run workspace/nested fmt/clippy/Rust, Python, profile/coverage/publication checks; compare old ID set explicitly. Obtain one fresh independent whole-P04 review; resolve actionable issues in one RED->GREEN fix pass.
- [x] Commit the fixed candidate and regenerate authenticated producer/fixtures in the existing managed clean worktree. Run combined required lane; missing tools/hardware never pass. Request independent artifact-only audit pinned to expected code/fingerprint/clean identity. Record actual statuses/count, not predicted passes.
- [x] Persist rulings, superseded rejection contracts, unsupported scope and exact native-tested identity in `docs/P04a-RESULTS.md`. Verify11 user hashes, staged/tracked/history/identity privacy scans; publish exact paths to existing draft workflow. No merge/release.

## Self-review and handoff

Spec1/2->Tasks6/7;3->Tasks1/2;4->Tasks3/4;5->Tasks4/5;6->Tasks6/7.
All five Review Focus cases have owning tests. Common globals survive legacy Kernel
wrappers without backend handles. Old load methods delegate with no globals; nullable
outputs and module-owned free/query semantics are explicit. The builder-check identity
gap includes legacy lookup-visible names/classes and has a RED test in Task1.
This is proposed detailed work, not implemented P04. Review the design and plan before
implementation, preserving main-agent inline execution and independent review.
