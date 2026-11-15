# Runtime Kernel Connection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** P09a2-B: run genuine nvcc CUDA executables unchanged through CT Runtime21, the same CT Driver and Intel Arc.

**Architecture:** CPU-only constructor callbacks own registration data; launch lazily materializes context-specific modules using five existing Driver APIs. Explicit leases and retirement separate host registration lifetime from native resources. Reuse P09a2-A's pure decoder and current primary-context policy.

**Tech Stack:** Rust/std, Windows x64 C ABI, MSVC/nvcc12, Python evidence replay, existing PTX/SPIR-V/Level Zero backend.

**Spec:** [kernel design](../specs/2026-10-22-runtime-kernel-design.md); prerequisite [decoder plan](2026-10-22-nvcc-fatbin.md).

The user's2026-10-22 "우선 1번하고 2번 하자" approves basic connection followed by default compiler extras. A/B implement the first of those user-facing stages. C remains the second, explicitly tracked below. The user approved these detailed plans with "가자"; Tasks1..6 are implemented. Task7 fixed candidate bf36cff passed41 clean required gates after independent whole-patch review and one regression-driven fix; independent fixed-artifact audit and publication scans passed. See [execution results](../../P09a2-RESULTS.md). Preserve main-agent implementation plus independent subagent review.

## Global Constraints

- Windows x64, EXE constructors first, app-local `cudart64_12.dll` + same pinned `nvcuda.dll`; Driver38 remains unchanged.
- Runtime21=existing14+7. First producer uses `--cudart=shared --cudadevrt=none`, non-RDC PTX8.0/sm52. Runtime22/default build is C, not an early whitelist exception.
- No ct-cuda/backend linkage in Runtime; only pure ct-fatbin path dependency. Preserve root Cargo and11 user files.
- Callbacks: no bridge, DLL loading/pinning, GPU/context/JIT, IO, native cleanup or waiting for active work. Release registry locks before Driver calls; unregister never locks a materialization gate.
- Limits:64 live registrations;1024 lifetime tokens;512 functions/registration;4096 live host mappings;1024 bytes/name;16MiB/image;64MiB owned raw images;128 loaded+retired native modules;64 TLS configurations. Budget801; detected fallible allocation2.
- Existing14 behavior/error mapping and all38 prior required gates remain. New errors are operation-specific; no general CUDA parity, framework/release/AMD/NVIDIA claim.
- Diagnostic unsupported host and qualified supported host are separate results; absent qualification stays unverified. No vendor files, raw logs, private paths or credentials published.

## Review Focus

1. Unregister while first native load is blocked must retire its late handle without resurrection (Task4, `unregister_during_load_owns_late_handle`).
2. A failed Push must not consume an older configuration or corrupt another thread (Task2, `failed_push_preserves_previous_and_other_thread`).
3. Equal symbol names across contexts must never share native handles (Task4, `same_symbol_two_contexts_isolated`).
4. Shape error9 must not swallow malformed argument error1 (Task4/6, `shape_and_argument_errors_differ`).
5. A successful child report with wrong DLLs or no actual launch must fail independent replay (Task6/7, `test_noop_and_forged_manifest_rejected`).

## Files and cross-task contracts

Create `crates/ct-cudart/src/{registration,registration_tests,configuration,kernel_driver,kernels,kernel_tests}.rs`.
Modify existing `lib.rs`, `errors.rs`, `driver.rs`, `platform.rs`, `state.rs`, nested `Cargo.toml`/`Cargo.lock` only as needed for listed contracts.

- `configuration.rs`: `#[repr(C)] #[derive(Clone,Copy)] pub struct Dim3 { pub x:u32,pub y:u32,pub z:u32 }`; `Config { grid:Dim3, block:Dim3, shared:usize, stream:usize }`; `push(Config)->i32`; `unsafe pop(grid:*mut Dim3,block:*mut Dim3,shared:*mut usize,stream:*mut c_void)->i32`. Final pointer is storage for stream pointer, not the stream value.
- `registration.rs`: opaque `Token=usize`, monotonic `RegistrationId=u64`; `Registry::new()->Self`; `unsafe register(&self,wrapper:*const c_void)->Result<Token,i32>`; `unsafe function(&self,token:Token,host:usize,symbol:*const u8,metadata:FunctionMetadata)->Result<(),i32>`; `end(&self,Token)->Result<(),i32>`; `retire(&self,Token)->Result<(),i32>`; `lease(&self,host:usize)->Result<LaunchLease,i32>`. `LaunchLease` holds registration ID, owned image reference, copied NUL-terminated symbol and active count, never unowned source pointers. `FunctionMetadata` stores thread_limit:i32 and five optional pointer identities as usize, never dereferenced. B accepts observed thread_limit=-1 and all optional pointers0; other valid metadata801.
- `kernel_driver.rs`: `Module=usize`, `Function=usize`. `KernelDriver:DriverCalls` adds `prepare_kernel(&self)->Result<(),i32>`, `attribute(&self,attribute:i32,device:i32)->DriverResult<i32>`, `load(&self,image:&[u8])->DriverResult<Module>`, `function(&self,module:Module,symbol:&[u8])->DriverResult<Function>`, `unload(&self,module:Module)->i32`, `unsafe launch(&self,function:Function,config:Config,args:*mut *mut c_void)->i32`. Only prepare_kernel returns Runtime-domain errors (including loader35), propagated unchanged before native methods. Other numeric errors are Driver codes and use operation-local mapping. Trait implementation shares existing DriverBridge; tests use a fake Driver implementing both traits.
- `kernels.rs`: `KernelRuntime { registry:Registry, cache:Mutex<Cache> }`; `unsafe launch<D:KernelDriver>(&self,runtime:&Runtime<D>,host:usize,config:Config,args:*mut *mut c_void)->i32`; `drain<D:KernelDriver>(&self,driver:&D,current:Context)->Result<(),i32>`. Returns Runtime codes; never cleanup in Drop. One lazy process instance constructed without GPU work.
- Cache key `(RegistrationId,Context)`; entry owns native slot reservation, optional Module, symbol→Function table, gate and explicit Loading/Live/Failed/Retired state. Native handle and reservation are process-owned even after errors. Lease Drop only decrements CPU count.

The seven C ABI signatures are fixed below (`uint3` has the same three-u32
layout as Dim3, but remains a distinct declared C type; CUDA stream is a pointer):

```c
void ** CUDARTAPI __cudaRegisterFatBinary(void *wrapper);
void CUDARTAPI __cudaRegisterFatBinaryEnd(void **token);
void CUDARTAPI __cudaUnregisterFatBinary(void **token);
void CUDARTAPI __cudaRegisterFunction(void **token, const char *hostFun,
    char *deviceFun, const char *deviceName, int thread_limit,
    uint3 *tid, uint3 *bid, dim3 *bDim, dim3 *gDim, int *wSize);
unsigned CUDARTAPI __cudaPushCallConfiguration(dim3 grid, dim3 block,
    size_t shared, void *stream);
cudaError_t CUDARTAPI __cudaPopCallConfiguration(dim3 *grid, dim3 *block,
    size_t *shared, void *stream_out);
cudaError_t CUDARTAPI cudaLaunchKernel(const void *hostFun, dim3 grid,
    dim3 block, void **args, size_t shared, cudaStream_t stream);
```

### Task1: CPU registration ownership and callback failures

**Files:** nested Cargo files, `registration.rs`, `registration_tests.rs`, `lib.rs` module wiring. **Consumes/produces:** Registry/LaunchLease contracts above; decoder Allocation→2, Invalid→218, Unsupported→801.

- [x] Write failing tests `registration_never_calls_driver`, `snapshot_survives_source_mutation`, `tokens_do_not_reuse`, `duplicate_and_end_policy`, `budgets_and_fallible_reservations`, `failed_mapping_does_not_poison_other_registration`. Assert wrapper24/magic0x466243b1/version1, version2→801, null→1; raw header is not a wrapper. Invalid image creates no token. No native/bridge callbacks occur even on retire.
- [x] Run `cargo test --manifest-path crates/ct-cudart/Cargo.toml --locked registration`; expect tests fail until implementation/lock update.
- [x] Verify clean tracked candidate's nested Cargo metadata accepts pure `ct-fatbin` path dependency; update only nested lock. Build Registry with stable process-lifetime token cells, fallible vector reservations, bounded image/name snapshots and tombstones. Preserve failed/retired identities until exit. Do not expose addresses of movable elements.
- [x] Account live registrations/mappings until retirement; image bytes until the last lease/cache reference releases owned bytes. Retire releases logical live counts immediately, never lifetime tokens/native reservations. Allocate/reserve before publishing; failures roll back counters; failed partial snapshots publish nothing. Successful boxed/Arc allocation can still abort on host OOM: document this limit instead of claiming catch_unwind catches it.
- [x] Implement policy: identical same-token mapping idempotent; conflicting same-token mapping→98 for that host; cross-token address ambiguous→98 while both live, retirement removes its live association. End on Building→Ready; repeated End on Ready succeeds; Function after End fails that registration1. Unknown/retired End or Function→98; known repeated Unregister succeeds, unknown Unregister records98. Failed tokens retain their relevant code until retire. Void callback errors remain scoped, and record nonzero TLS without clearing on success.
- [x] At the ABI boundary validate both deviceFun and deviceName as bounded NUL-terminated names before retaining either; the observed B producer supplies equal names. Unequal names return scoped801 rather than guessing a symbol. HostFun is an opaque nonzero identity, not a C string. Tests assert null names/host1, mismatched names801,1025-byte names801 and overwritten caller name storage cannot alter an existing mapping.
- [x] Run nested tests and clippy; expect exact bounds64/65,1024/1025,512/513,4096/4097,1024/1025 bytes,64MiB/+1 covered using reduced test-only resource limits where large allocation is unnecessary; production constants also asserted. Commit `feat: own CPU CUDA registrations`.

### Task2: Launch configuration and ABI containment

**Files:** `configuration.rs`, `lib.rs`, `errors.rs`; test in `configuration.rs`. **Interfaces:** Config/Dim3 above; seven final signatures specified in design section6 and Task5's header checks.

- [x] Write failing `failed_push_preserves_previous_and_other_thread`, `pop_validates_all_outputs_before_consuming`, `configuration_capacity`, `callback_panic_boundaries`: assert LIFO,64 succeeds/65th801, zero axis9, shared/non-null stream801; any null Pop output1 retains top; empty9. Success preserves prior TLS, failure sets it, Get clears and Peek retains.
- [x] Run `cargo test --manifest-path crates/ct-cudart/Cargo.toml --locked configuration`; expect new tests fail.
- [x] Implement GPU-free fallible TLS Vec stack; reserve before push. Add pointer-return and void callback catch_unwind boundaries (panic999/null or scoped failure), alongside existing integer boundary. Push ABI returns u32, Pop i32, callbacks void except FatBinary→pointer. Add static names/descriptions for9/98/218/400 after independently checking pinned official enums. No allocator-abort containment claim.
- [x] Run nested tests/clippy; assert Dim3 size12/alignment4 and no GPU work. Do not publish export whitelist21 yet. Commit `feat: add bounded CUDA launch configuration`.

### Task3: Lazy extension of the same Driver bridge

**Files:** `kernel_driver.rs`, `driver.rs`, `platform.rs`, existing `tests.rs`. **Interfaces:** KernelDriver above; platform adds `resolve_kernel<P:Platform>(platform:&P,owned:&P::Owned)->Result<[usize;5],i32>` in fixed order LoadData/GetFunction/LaunchKernel/Unload/DeviceGetAttribute.

- [x] Add `missing_kernel_extension_preserves_memory_calls`, `kernel_extension_is_complete_and_cached`, `kernel_symbols_belong_to_owned_module`: missing any one symbol or forwarding to another module fails35 before a partial table can be used; each resolution failure cached once. Assert actual exported Launch returns35 unchanged, not999 through from_driver, while existing14 memory calls succeed without resolving extension symbols.
- [x] Run nested tests; expect extension tests fail.
- [x] Add OnceLock<Result<[usize;5],i32>> to existing owned/pinned DriverBridge. Use its module identity/held references, no new LoadLibrary or second Driver state. Resolve all five before publishing. Implement typed extern system calls; Launch passes shared0/streamNULL/extraNULL as already validated, and borrowed argument storage only during synchronous Driver call.
- [x] Run nested tests/clippy and existing bootstrap tests; expect all pass. Commit `feat: extend pinned Driver bridge for kernels`.

### Task4: Context-specific materialization and explicit retirement

**Files:** `kernels.rs`, `kernel_tests.rs`, `lib.rs`; reuse existing `Runtime::ensure_current`. **Interfaces:** KernelRuntime/cache/leases above.

- [x] Add fake-Driver tests `same_symbol_two_contexts_isolated`, `first_use_loads_once`, `unregister_during_load_owns_late_handle`, `lookup_failure_retains_module`, `retirement_at_capacity`, `cleanup_failure_never_retries`, `stale_context_never_resurrects`, `shape_and_argument_errors_differ`. Use barriers for load-vs-unregister and parallel first use. Assert exact load/get-function/launch/unload counts, zero Driver calls inside registry lock or callbacks.
- [x] Run nested kernel tests; expect fail before implementation.
- [x] Implement launch order: acquire Ready mapping lease; reject shared/stream/zero axes; preserve existing current context via ensure_current; prepare_kernel and propagate its Runtime-domain error unchanged; query actual context device and attributes1..7; reject nonpositive caps999; checked block volume/axis/grid caps and widened grid*block per-axis>u32MAX→9. Arguments rejected by Driver1 remain1. Do not blanket-map Driver1 to9.
- [x] Materialize using per-key gate outside registry lock; reserve native slot before load. Check retirement when publishing, placing late module in Retired even when an older lease can finish. Success-load/failure-lookup always owns handle. Failed materialization is sticky per key; known failed load without handle returns reservation, uncertain outcome retains it. No concurrent retry or capacity eviction.
- [x] Retire by CPU state under registry lock only, marking all keyed entries through a shared retirement flag; never take their gate. Drain only from explicit launch entry with matching current context and no active leases, outside registry lock. Never switch context for cleanup. Successful unload releases slot; failure retains handle/reservation and one sticky failure, no retry. Ineligible contexts remain bounded retained. Runtime operations never resurrect stale709.
  Execution refinement: also drain at explicit cudaDeviceSynchronize, after ensuring the caller's current context. Otherwise retiring every registration at the raw-image budget could prevent creating any new registration capable of reaching Launch to reclaim it. No new cleanup occurs in callbacks/destructors. Bound all native ownership/cache records at128, including safe failed-load tombstones, while releasing known failed loads' actual native reservation; this conservatively bounds failed-context metadata. Cache missing-function errors per symbol so another valid kernel in the same module can run. These refinements are tested and recorded in the execution ledger.
- [x] Reserve cache/retirement-record storage before native load; after load, publication and retire transitions allocate nothing. At capacity, unregister only changes preallocated CPU state. Fault tests inject reserve failure before load and lookup failure after load, proving no native handle is lost through an allocation error.
- [x] Add operation-local errors: load218→218; load/function/launch400→400; lookup500→98; other codes use existing explicit map. Unknown/retired/ambiguous mapping98, malformed fields1, unsupported801. Run nested Rust suite/clippy; expect original14 tests still pass. Commit `feat: launch registered kernels with context lifetimes`.

### Task5: Independent ABI proof and closed Runtime21 profile

**Files:** `include/ct_cudart.h`, `tests/p09a_runtime.def`, `tests/runtime_reference_abi.cpp`, `tests/runtime_declared_abi.cpp`, `scripts/check_runtime_abi.ps1`, `scripts/runtime_abi_evidence.py`, `scripts/check_runtime_profile.py`, `docs/compatibility/runtime-profile-v1.json`, `tests/test_runtime_profile.py`, `scripts/ct.py`, `tests/test_ct_loader.py`.

- [x] Add failing header/profile/import tests for exact21; reject22nd RegisterVar, other cudart versions, ordinals/delay imports/static form. Preserve default Driver-only rejection. Header parser must recognize `__cuda*` as well as `cuda*`; maintain closed schema and actual export/DEF parity.
- [x] Run `python -m unittest discover -s tests -p test_runtime_profile.py` and matching `test_ct_loader.py`; expect21 cases fail initially.
- [x] Add seven declarations, actual Rust extern system exports and DEF entries. Independent official-header TU asserts each original function pointer type, unsigned Push, Pop's void* stream output and Dim3 by-value; declared TU checks CT types against typed Rust exports using native calls, not size assertions alone. Probes use distinct grid/block/size_t/stream sentinels, pointer/void returns, and registry failures. Header closure includes original transitive compiler-runtime headers authenticated by A's recipe.
- [x] Extend native ABI evidence/audit to actual21 exports and probes; test missing/changed DLL/header/output, stale manifest and capture spoof. Run pinned ABI script and independent audit; require actual successful probes, not child JSON alone.
- [x] Only after the new native ABI gate exists, extend exact opt-in Runtime whitelist/manifest21 and bundle hashes, retaining original EXE bytes. Run nested tests/profile checker/Python tests and ABI command again. Commit `feat: expose verified Runtime21 kernel ABI`.

### Task6: Genuine nvcc program on Arc with an independent oracle

**Files:** extend A's `tests/fixtures/p09a2/vector.cu`, create `tests/fixtures/p09a2/{multi_kernel,module_a,module_b}.cu`, `tests/p09a2_kernel_control.cpp`, `tests/p09a2_noop_driver.c`, `tests/p09a2_kernel_check.py`, `tests/test_kernel_evidence.py`, `scripts/run_p09a2_smoke.ps1`. Reuse producer recipe; never replace generated stub with a handwritten launcher for the primary result.

**Interfaces:** checker `audit_manifest(path:Path,root:Path,*,execute:bool=False)->list[str]`; smoke script `-HostProfile diagnostic|qualified` writes ignored `.cache/p09a2-kernel-latest.json`. Native manifests bind actual source/producer header closure/flags/EXE/imports/fatbin/Runtime/Driver hashes, seed, host qualification and complete result arrays.

- [x] Add failing `test_noop_and_forged_manifest_rejected`, `test_changed_exe_or_dll_rejected`, `test_wrong_imports_rejected`, `test_diagnostic_cannot_claim_qualified`, `test_child_success_without_arrays_rejected`. Independent Python computes unsigned arithmetic, guards and input preservation from seed, not expected arrays supplied by child.
- [x] Run evidence unittests; expect missing checker failures.
- [x] Implement genuine fixtures:17 values and4 guards, non-divisible2x16 grid; same-name kernels in two separately generated modules; repeated and parallel first use; ordinary Driver context preservation and two-context execution; unregister/teardown and argument/shape errors. Control harness may orchestrate contexts and invoke registered entry addresses, but genuine generated constructors and launch stubs remain the positive application path. All GPU operations use actual CT Runtime/Driver.
- [x] Verify original EXE/fatbin hashes before/after bundle; no source/binary rewrite. Add wrong/no-op launch-provider control: it may return0 but oracle must reject unchanged/incorrect arrays. A direct PTX run or callback observer is supplementary only.
- [x] Run smoke diagnostic and independent `execute=True` replay with fresh seeds; expect every positive numeric/guard/input assertion pass and every no-op control fail. Attempt qualified only if authenticated supported host exists; otherwise record unavailable, never qualified pass. Keep callbacks free of tracing IO; any observations come from post-main test instrumentation/manifest assembly.
- [x] Run evidence Python tests and retain actual artifacts ignored; commit CT-owned fixtures/scripts only: `test: execute genuine nvcc programs through CT Runtime`.

### Task7: Required gates and clean candidate acceptance

**Files:** `scripts/run_validation.py`, `tests/test_kernel_evidence.py`, `docs/compatibility/{coverage-v1,toolchain-lock-v1}.json`, `docs/P09a2-RESULTS.md`, `.github/workflows/cpu.yml` only if a new CPU command is necessary.

**Interfaces:** add required diagnostic gates `producer.nvcc_fatbin` (A recipe replay), `arc.runtime_kernel_abi` (new21 ABI evidence), `arc.runtime_kernel` (actual diagnostic native program). Existing `arc.runtime_abi` still verifies original14 probes as a subset; original `arc.runtime` retains original memory/control checks. Qualified producer/native evidence is a separate opt-in qualification report, not a hidden replacement for required diagnostic gates. No predicted pass count.

- [x] Add failing evidence/runner tests: stale latest pointer removed before launch; capture reexecutes each native program with fresh seed; subsequent bundle audit rehashes/reconstructs inputs; missing artifact or child success alone fails. All38 previous gate IDs remain present, with no duplicate new case IDs.
- [x] Run Python discovery; expect newly added cases fail before runner integration.
- [x] Integrate three exact IDs/commands/catalog anchors/tool IDs and artifact input roles. Keep closed report/config schemas, correct execution kinds and source/config fingerprints. CPU discovery/nested Runtime tests cover new semantic tests; retain hardware absence as unavailable, never native pass. Runtime kernel ABI invokes the expanded ABI checker but has its own explicit evidence role/subset assertions.
- [x] Run root fmt/clippy/tests, nested fmt/clippy/tests, Python discovery and registry/profile/publication checks once changes settle. Obtain independent whole-patch review; fix actionable issues with targeted checks.
- [x] Commit fixed candidate; reuse attached clean worktree and authenticated ignored tools. Run `python scripts/run_validation.py --lane combined --required --output-directory results/local/p09a2-clean`; independently audit bundle and genuine native artifacts. Any missing required tool/GPU or failure prevents completion. Record exact commit/fingerprint, gate statuses, diagnostic/qualified distinction and release_claim=false in results.
- [x] Compare11 user-file SHA values to the existing local baseline; scan staged/tracked public artifacts and noreply Git identity; commit only explicit approved paths and attach/update existing draft PR. No merge/release. Request independent clean-artifact audit before reporting success.

## Second user-facing stage: default compiler extras (P09a2-C)

After A/B pass, proceed in the user's requested order to a separate C design/plan. Required contract is already fixed: Runtime22 adds `__cudaRegisterVar`; version2 contains a bounded null-terminated array of raw prelinked fatbin pointers, not wrapper pointers. Empty own payload does not mean no dependencies. Design traversal/alias/cycle/image budgets, owned variable metadata, and deferred unused-module handling before implementation. Generic unused registrations may defer native materialization; used unsupported globals/functions must fail deterministically, without vendor-name exceptions.

C acceptance uses the default nvcc build of the same original source: constructor→launch→Arc numeric/guard/input results, plus an actual used-unsupported-variable negative fixture. Extend whitelist22 only with corresponding ABI/evidence. Full globals/device-link semantics remain P03/P04 work. A/B completion must not be described as C/default-nvcc compatibility.

## Self-review and handoff

Spec sections1..10 map to A Tasks1..3 and B Tasks1..7; C is explicitly retained rather than silently implemented as no-op callbacks. All five Review Focus cases have owning tests. Independent read-only review identified an extension loader35/Driver-error-domain mismatch; prepare_kernel now preserves that Runtime code separately, with an exported Launch assertion. Decoder fault injection and Driver mapping tests are separated to respect dependency cfg(test) boundaries. Implementation status: Tasks1..6 complete. Task7 fixed candidate bf36cff passed41 clean required gates after independent review and one regression-driven fix; independent fixed-artifact audit and publication scans passed. Historical plan-review findings above were resolved before implementation. Implementation rulings and evidence are recorded in the results document.
