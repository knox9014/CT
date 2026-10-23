# Default Device Runtime Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Main-agent inline implementation with independent review is preserved. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** P09a2-C: run unchanged shared-cudart executables using default device-runtime linkage on Intel Arc, while rejecting used unsupported variable/link semantics.

**Architecture:** Separate bounded structural container inspection from executable decoding. Own version2 raw dependencies and variable metadata in CPU registration records. Expose only eligible version1/no-variable images to the existing context-keyed lazy kernel cache. Add one typed Runtime callback and independent default-link evidence.

**Tech Stack:** Rust/std, Windows x64 C ABI, pinned CUDA12.0.76/MSVC diagnostic recipe, Python evidence replay, existing CT Driver/Intel backend.

**Spec:** [default device-runtime design](../specs/2026-10-23-default-device-runtime-design.md).

Status: proposed detailed plan for review; no C product implementation started. Existing A/B detailed approval does not claim these C interfaces already exist.

## Global Constraints

- Shared cudart, non-RDC PTX8.0/sm52; omit `--cudadevrt=none`. No static-cudart claim.
- Runtime22 adds only RegisterVar; same pinned Driver, no backend linkage/new GPU calls in constructors.
- Structural metadata acceptance never implies executability. Version2 or any variables/token => launch801 before bridge/context/native calls. No symbol-name exceptions or partial linking.
- Preserve16MiB/image,64MiB total owned raw bytes,64 live/1024 lifetime tokens,512 functions/token,4096 function mappings,1024-byte names,128 native records,64 TLS configs. Add32 dependency slots plus null,256 vars/token,2048 live variable mappings; size1..16MiB metadata only.
- Preserve first token failure, retired/unknown98, post-End1, original14 memory behavior and all41 gate IDs.
- Preserve11 original user files, `.gitignore`, exact staging, publication scans. Vendor assets/observations/logs stay local. Diagnostic is not qualified; no release/AMD/NVIDIA/framework claim.

## Review Focus

1. A self/duplicate raw pointer must not create recursion or double-charge within a token: Task2 alias/list/header tests.
2. Failure copying a late dependency must not publish a half-owned token or leak global budget: Task2 fault/rollback tests.
3. Concurrent retire during variable name preparation must not restore Building or change a terminal error: Task3 barrier test.
4. An otherwise valid kernel with one unused global must still be blocked, while another token runs: Task3 fake-Driver and Task6 native controls.
5. An old or no-op DLL/EXE or fabricated801 report must not pass the new gates: Tasks4/6/7 artifact mutation and independent replay.

## File structure and task interfaces

Create focused Runtime modules `registration_images.rs` and `registration_variables.rs`;
keep Registry state/budget synchronization in registration.rs and native ownership
in kernels.rs. Test these modules through registration image/variable test modules.
Create C producer/ABI/native evidence separately; retain old41 recipe identities.
No root Cargo changes or new third-party dependencies are needed.

### Task1: Structural-only raw container inspection

**Files:** Modify `crates/ct-fatbin/src/lib.rs`; test `crates/ct-fatbin/tests/decoding.rs`.

**Produces:** `pub struct ContainerInfo { pub record_count:u16,pub ptx_records:u16,pub machine_records:u16 }` and `pub fn inspect_container(image:&[u8])->Result<ContainerInfo,Error>`.

- [ ] Add tests `structural_inspection_is_not_executable_acceptance`: empty16 and nine kind2 records structurally pass, but existing extract_candidates rejects both801; valid PTX still decodes unchanged. `structural_limits_and_extents` asserts exact/truncated/overflow extents, zero/unaligned payload, header64..4096 alignment8, version/kind rejection and record256/257 boundary,16MiB cap.
- [ ] Run `cargo test -p ct-fatbin`; expect missing inspection interface failures before implementation.
- [ ] Implement the spec's outer structure checks with checked arithmetic; no PTX decompression/profile acceptance or record-specific instruction interpretation. Keep old extractor tests intact; share structural helpers only when errors/strictness remain identical.
- [ ] Run `cargo test -p ct-fatbin` and `cargo test -p ct-cuda images`; expect all existing/new CPU tests pass. Run fmt/clippy for affected crates.
- [ ] Commit exact decoder/test paths: `feat: inspect bounded raw fatbin structure`.

### Task2: Owned version2 dependency lists and aggregate lifetime

**Files:** Create `crates/ct-cudart/src/registration_images.rs`, `registration_image_tests.rs`; modify `registration.rs`, `kernels.rs`, `lib.rs` module declarations/launch preflight and existing registration/kernel test fixtures as needed.

**Consumes:** Task1 inspection and existing image_size/extract_candidates.
**Produces:** `OwnedImages { primary:Vec<u8>,prelinked:Vec<Vec<u8>>,version:u32,raw_bytes:usize }`; `unsafe copy_images(wrapper:*const c_void,remaining:usize)->Result<OwnedImages,i32>`. Image owns the aggregate raw-byte charge, released once on Drop. Registration publication remains atomic under its current mutex. Change `LaunchLease::image(&self)->Result<&[u8],i32>` here, with version2 returning801 and version1 returning its primary bytes; update all callers together.

- [ ] Add `version2_owns_raw_dependencies_and_deduplicates_aliases`, `dependency_slot32_requires_null`, `wrapper_is_not_a_raw_dependency`, `empty_dependency_list_rejected`, `dependency_copy_failure_rolls_back`, `retired_lease_keeps_all_image_bytes`. Use CT-owned buffers with valid caller-readable extents; mutate/drop source buffers after callback, then compare snapshots. Self-alias primary is charged once; same bytes/different addresses charged twice. Failures leave no token/count/budget changes.
- [ ] Run `cargo test --manifest-path crates/ct-cudart/Cargo.toml --lib registration_image_tests`; expect missing module/type failures.
- [ ] Implement version1 unchanged strict decoding/extra=null. Implement version2 own structural image plus nonnull raw list,1..32 entries and required slot32 null; no recursion. Validate fixed header/budget before full slices/allocation; deduplicate pointer identities only within token, discard identities after owned copies. Enforce33 unique images maximum and global64MiB including retained leases/cache. Map errors1/2/218/801 as spec.
- [ ] Run all nested Runtime tests/fmt/clippy; verify no Driver calls from registration. Check image eligibility in exported launch preflight before bridge initialization and in KernelRuntime before ensure_current; version2 is blocked while CPU leases still own its complete snapshot through retirement.
- [ ] Commit explicit Runtime paths: `feat: own bounded prelinked registration images`.

### Task3: Variable ownership and fail-closed image eligibility

**Files:** Create `registration_variables.rs`, `registration_variable_tests.rs`; modify `registration.rs`, `kernels.rs`, existing registration/kernel tests. Add module declarations only in `lib.rs`; export wiring is Task4.

**Produces:** `VariableMetadata { external:i32,size:usize,constant:i32,global:i32 }`; Registry `unsafe variable(token:Token,host:usize,address:*const u8,name:*const u8,metadata:VariableMetadata)->Result<(),i32>`. Task2's `LaunchLease::image` eligibility extends to any variable in its token (version2 remains blocked). Shared builder helper may be renamed to registration_state when both function/variable use it; update all consumers in the same task.

- [ ] Add tests `variable_metadata_is_owned_and_bounded`, `variable_duplicate_conflict_and_capacity`, `variable_terminal_state_precedes_payload`, `retire_during_variable_preparation_cannot_resurrect`, `variable_blocks_only_its_registration`. Assert spec's flag/name/size errors,256/257 and2048/2049 limits, first-failure retention, retired98, post-End1, successful TLS preservation (exported part in Task4). Use a deterministic test-only barrier outside the registry lock for retire race; do not depend on scheduling sleeps.
- [ ] Run nested tests; expect absent variable API and missing eligibility errors.
- [ ] Implement owned two-name metadata and opaque host identity, idempotence/conflict1, independent variable budget and retirement release. No allocation proportional to size. Prepare outside lock with terminal-state checks before reads and again under lock. Never overwrite existing failure. Lease snapshots version/variable restriction; existing eligible active leases remain safe through retire.
- [ ] Extend Task2's image eligibility in both exported launch preflight and KernelRuntime launch, before bridge/current-context/extension. Fake Driver asserts zero calls for v2/variable modules and normal no-variable sibling execution. No module selection/linking from dependencies occurs.
- [ ] Run full nested Runtime tests/fmt/clippy; verify Task2 image() callers/tests still consume Result without bypasses. Re-run registration race/error regressions and native-lifetime fake tests.
- [ ] Commit exact paths: `feat: retain variables and reject unsupported module use`.

### Task4: Independent RegisterVar ABI and Runtime22 admission

**Files:** Modify `lib.rs`, `include/ct_cudart.h`, `tests/p09a_runtime.def`, `docs/compatibility/runtime-profile-v1.json`, `scripts/check_runtime_profile.py`, affected profile tests and `tests/runtime_kernel_native_abi.cpp`; create `tests/runtime_default_reference_abi.cpp`, `runtime_default_declared_abi.cpp`, `runtime_default_native_abi.cpp`, `scripts/check_runtime_default_abi.ps1`, `runtime_default_abi_evidence.py`, `tests/test_default_abi_evidence.py`.

**Produces:** exact `void __cudaRegisterVar(void **,char *,char *,const char *,int,size_t,int,int)`; signature ID `void(ptr_ptr,char_ptr,char_ptr,const_char_ptr,i32,size,i32,i32)`. Evidence `audit(path:Path,root:Path,*,execute:bool=False)->list[str]`; local pointer `.cache/p09a2c-abi-latest.json`, case `arc.runtime_default_abi`.

- [ ] Add exported CPU-only tests for valid metadata/no TLS clearing; null/mismatch/budget failures; first failure and retired precedence. Add original pinned host_runtime.h and independent CT-header type static_asserts,8-byte size_t sentinels, original21-address availability plus exact22-export parity in actual Rust DLL.
- [ ] Build declaration probes using authenticated A producer/header closure and fresh Runtime DLL; wire callback through panic/TLS boundary to Registry.variable. Before invoking the Driver loader in cudaLaunchKernel, check lease.image()? alongside existing host/config preflight. Actual DLL typed calls prove metadata acceptance, blocked801, and unaffected no-variable kernel preflight9/98; no fake implementation counts as proof.
- [ ] Run `powershell -NoProfile -File scripts/check_runtime_default_abi.ps1`; expect typed reference/declared/actual DLL and missing/forwarded controls pass, with independently hashed artifacts/replay. Only after this proof update header/DEF/profile/checker/loader admission22 atomically.
- [ ] Keep BASE_SIGNATURES14 and introduce KERNEL_SIGNATURES21 separate from current SIGNATURES22. Update old kernel native probe's current-DLL export expectation to22 without removing any21-function typed assertions; new gate independently checks RegisterVar/full22. Preserve old14 expected output/import fixtures. Audit old scripts/tests for hardcoded21 counts, and bind any changed probe source hashes explicitly.
- [ ] Run profile/loader/Python tests plus existing old Runtime ABI and kernel ABI gates. Mutating a symbol/count/type or substituting an old21 DLL must fail the new audit, while historical14 import fixtures remain14.
- [ ] Commit exact ABI/profile paths: `feat: verify and admit Runtime variable registration ABI`.

### Task5: Authenticated default-link producer and CPU observations

**Files:** Create `scripts/prepare_nvcc_default.py`, `tests/p09a2c_registration_observer.cpp`, `tests/test_nvcc_default_probe.py`, `docs/compatibility/nvcc-default-producer.md`; reuse unchanged `tests/fixtures/p09a2/vector.cu` and current authenticated A manifest/tool pins. Extend host preparation helpers only if required, without changing old manifest/command semantics.

**Produces:** `audit_default_producer(path:Path,root:Path)->list[str]`; CLI `prepare --base-manifest .cache/p09a2-producer/manifest.json --output .cache/p09a2c-producer` and `replay --manifest ...`. New manifest schema1 has exact fields `schema_version,base_producer,source,commands,host_profile,artifacts,observations`; base_producer binds path/hash and must pass audit_probe. New case `producer.default_device_runtime`.

- [ ] Add tests `default_recipe_cannot_hide_nodevrt_flag`, `default_probe_rejects_mutated_dependencies`, `default_probe_requires_owned_observations`, `default_probe_never_qualifies_diagnostic`. Hidden NVCC/CL flags, relabeled host, changed raw dependency/EXE/header/observer outputs or missing terminator must fail.
- [ ] Run unittest discovery for the new probe file; expect missing helper failures.
- [ ] Regenerate the CT-owned vector source byte-identically using current pinned compiler/host environment normalization, explicit ccbin, shared cudart, PTX8/sm52 and omitted cudadevrt flag. Bind source/EXE/fatbin/generated constructor files and full original package/header/library/tool closure via authenticated base manifest. Do not edit vendor headers, EXE or PTX.
- [ ] A bounded CT-owned CPU observer records wrapper versions, raw pointer-list shape, copied raw image artifacts, function counts/metadata/optional-pointer presence and owned variable field values; fails allocation and never claims execution. Its source/binary/input/output hashes and expected controlled exit11 are audited. Product rules must never depend on those generated symbol names. Diagnostic/qualified distinction remains inherited, not self-declared.
- [ ] Run prepare and independent replay; expect v1/v2 dependencies and metadata reconstructed from actual artifacts. Preserve original A producer recipe and manifest. No vendor bytes/logs tracked.
- [ ] Commit only CT-owned files: `test: authenticate default device-runtime producer inputs`.

### Task6: Default-link native numeric and used-global negative oracle

**Files:** Create `tests/fixtures/p09a2/default_used_global.cu`, `tests/p09a2c_default_control.cpp`, `tests/p09a2c_counting_driver.c`, `tests/p09a2c_default_check.py`, `tests/test_default_runtime_evidence.py`, `scripts/run_p09a2c_smoke.ps1`; reuse original oracle/module source bytes and existing no-op proxy. Any Driver control DEF is CT-owned and explicit.

**Produces:** `audit_manifest(path:Path,root:Path,*,execute:bool=False)->list[str]`; local `.cache/p09a2c-default-latest.json`, case `arc.runtime_default`. Manifest pins source/config/host/producer/imports/EXE/fatbin/DLL/seed/complete readbacks and negative controls.

- [ ] Add failing Python tests for wrong arrays/guards/inputs, changed EXE/DLL/dependencies/imports, stale pointer, missing arrays, forged801 report and no-op launch. Require an exact declared mode set, independent expected values and explicit host qualification.
- [ ] Compile original kernel_oracle/module_a/module_b source bytes with shared cudart and default device-runtime linkage, with no source/binary edits or removed registrations. Run single/repeat/ordinary/two_contexts/parallel/multi_module and independent fresh-seed numerical replay. Keep17 results+4 guards and both21-element input arrays. Do not reuse B boundaries mode's expected801 when RegisterVar is now implemented.
- [ ] Add actual-used volatile device-global CU and no-variable sibling. Bind generated registration and original PTX showing the global load survived optimization. Registration returns success and enters main; launch returns801; supported memory/sync/free behavior still works. A typed manual sibling/control with forwarding counters independently proves blocked launch performs zero context/load/launch calls and a valid sibling still executes actual Arc. Unknown/v2 functions cannot evade this gate by renaming.
- [ ] Run no-op-launch provider; numeric oracle must reject successful child exit with unchanged outputs. Re-execute positive and negative artifacts independently and rehash originals afterward. Callback observer/direct PTX demos are supplementary only.
- [ ] Run new smoke plus existing arc.runtime/arc.runtime_kernel gates and evidence tests. Retain diagnostic label unless a separately reviewed supported host is provisioned.
- [ ] Commit exact CT-owned paths: `test: execute default-linked CUDA programs on Arc`.

### Task7: Required gates, fixed clean candidate and review

**Files:** Modify `scripts/run_validation.py`, `tests/test_validation_runner.py`, `docs/compatibility/coverage-v1.json`; create `docs/P09a2C-RESULTS.md`. Update existing draft PR description only after checks.

- [ ] Add failing runner tests retaining all41 prior IDs and adding only producer.default_device_runtime, arc.runtime_default_abi and arc.runtime_default. Cover explicit source/config input hashes, stale-pointer clearing, capture-time independent fresh execution, later artifact rehashing and producer provenance reconstruction. Child success alone never passes.
- [ ] Implement exact commands/catalog IDs/evidence roles and closed manifest validation; keep old41 gates active. Existing A producer commands and old memory/kernel oracles remain required subsets, not silently replaced by C.
- [ ] Run root/nested fmt, clippy, Rust suites, Python discovery and profile/coverage/publication checks. Request one fresh independent whole-C review focused on spec's five cases, including malformed ignored modules and error precedence. Fix actionable findings with reproduced RED->GREEN; record any bounded decisions/minors.
- [ ] Commit fixed code candidate. Reuse the managed clean worktree and authenticated local tools; regenerate C producer there. Run `python scripts/run_validation.py --lane combined --required --output-directory results/local/p09a2c-clean`. All required cases must actually pass; missing GPU/tool is not success.
- [ ] Request independent read-only bundle reconstruction pinned to actual code/fingerprint/clean identity and authentic artifacts. Record host qualification, supported boundary, unavailable hardware and release_claim=false; do not predict passes from the plan.
- [ ] Verify all11 original file SHA values; stage exact CT-owned paths, scan staged/tracked/history and noreply Git identity. Publish results/doc-only commit and update the existing draft PR; retain worktree and no merge/release.

## Self-review and handoff

Spec1/2->Tasks5/6;3->Tasks2/3/6;4->Tasks1/2;5->Tasks3/4;
6->Tasks1..7;7->Tasks4..7;8 remains excluded. All five Review Focus cases have
owning tests. The new structural inspector does not widen executable acceptance;
OwnedImages aggregation replaces the single-image budget once; variable use blocks
before Driver initialization; ABI22 is admitted only after actual native proof.
This is a proposed plan, not a run result. Review the new detailed design/plan before
product implementation; preserve the already selected inline execution method.
