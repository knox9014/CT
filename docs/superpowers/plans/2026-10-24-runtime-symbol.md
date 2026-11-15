# Runtime Symbol APIs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline;
> one independent whole-change review, one fix pass, then artifact-only audit.

**Goal:** unchanged genuine CUDA programs use synchronous symbol APIs through the
same stored u32 module as kernel launch, with Runtime26 and Driver39.
**Architecture:** opaque SymbolLease plus shared context-keyed module initialization;
query/copy under the entry gate, immutable bindings and existing Driver transfers.
**Tech Stack:** Rust/std, original CUDA12 headers, diagnostic nvcc, Windows x64 Arc.
**Spec:** ../specs/2026-10-24-runtime-symbol-design.md.

## Global Constraints

Version1/flags0/size4 only; no hidden kernel args/dependencies/second loader/cache.
Old22 ABI subset verified; four additive exports, Driver39 unchanged. Opaque host
symbols; unknown/null/retired/ambiguous13; stable query outputs on all errors.
To kinds1/3, from2/3;4 ->801, others21. Checked offset+count<=4; zero count validates
symbol, permits null data and offset<=4, skips native copy. Preserve first-failure,
active lease/retire/drain and last-error semantics. Keep48 IDs; add exactly2 ->50.
Preserve11 original user files, private cache evidence and existing draft workflow.

## Review Focus

1. Symbol-first and launch-first access must not create separate initialized copies.
2. Unregister while binding/copy blocks must not lose data or unload the native module.
3. Invalid symbol/query/provider failures must preserve outputs and scoped errors.
4. Partial/zero/overflow/D2D cross-context copies must not bypass extent ownership.
5. New ABI/profile/capture proof must not weaken any old48 case or forge success.

### Task1: Symbol leases and shared native module/bindings
Files: crates/ct-cudart/src/{registration,kernels,kernel_tests,registration_variable_tests}.rs.
- [ ] Add RED symbol registry and shared-module tests; run nested lib tests.
- [ ] Add SymbolLease/common RegistrationData access, opaque index lookup and counts.
- [ ] Refactor common module initialization/gate; reserve and retain global bindings.
- [ ] GREEN old/new nested suites, fmt/clippy; commit exact paths.

### Task2: Four APIs, copy policy and additive ABI/profile
Files: new crates/ct-cudart/src/symbols.rs and symbol tests; lib.rs/errors.rs;
include/ct_cudart.h, tests/p09a_runtime.def; runtime profile/checker/tests.
- [ ] RED output preservation, lookup, direction/range/zero/overflow, TLS error and
  deterministic unregister/query/copy tests using fake Driver calls.
- [ ] Implement queries/transfers under common module gate; error13 text; no new Driver.
- [ ] Add four signatures/exports, preserve old22 assertions, correct stale profile limits.
- [ ] GREEN nested full tests, ABI/static profile checks, fmt/clippy; exact commit.

### Task3: Original-header ABI and genuine native symbol consumers
Files: new tests/runtime_symbol_* probes, tests/fixtures/p04b/*.cu, independent
symbol oracle/control sources and scripts/check_runtime_symbol_abi/run_p04b helpers.
- [ ] RED independent oracle/tamper tests and exact original prototype assertions.
- [ ] Build actual default-device-runtime/shared-cudart EXE; symbol-first/launch-first,
  partial copies, queried-address memcpy, two contexts, guards/input and retire controls.
- [ ] Run actual Arc positive/no-op/missing/foreign controls and fresh replay; bind
  exact compiler/Cargo outputs/commands/inputs/roles, not exit-zero child claims.
- [ ] GREEN old/new ABI and native checks; commit CT-owned source only.

### Task4:50 required cases, clean acceptance and independent audit
Files: scripts/run_validation.py, evidence auditors, runner tests, coverage/results.
- [ ] RED tests retain all48 and add only arc.runtime_symbol_abi/arc.runtime_symbol;
  stale-pointer, forged-success, source/config/raw/binary tamper and capture replay.
- [ ] Integrate strict proof and run appropriate complete suites. Independent review
  entire change, regrade and one TDD fix pass; record all rulings/minors.
- [ ] Freeze candidate; clean checkout full required50 with native replay. Artifact
  audit pins actual commit/fingerprint/clean state and rehashes before/after.
- [ ] Record actual outcomes/scope, verify11 user hashes/privacy, publish draft only.

## Exact interfaces and review test ownership

Task1 introduces Registry::symbol(host:usize)->Result<SymbolLease,i32>,
SymbolLease { data:Arc<RegistrationData>, variable_index:usize } and its active-count
Drop; RegistrationData::{image,variables,retired} share eligibility/access with
LaunchLease. KernelRuntime::entry(data:&Arc<RegistrationData>,context:Context)
returns the existing shared cache Entry. ensure_module(driver:&D,data:&Arc<RegistrationData>,
state:&mut EntryState)->Result<Module,i32> owns load/validation once. EntryState gains
bindings:Vec<Binding {pointer:u64,size:usize}> reserved before native module load.
KernelRuntime::with_symbol<D:KernelDriver,T>(&self,rt:&Runtime<D>,lease:&SymbolLease,
action:impl FnOnce(&D,u64,usize)->Result<T,i32>)->Result<T,i32> holds the gate and
maps raw action Driver errors after recording fatal400/709. The exported caller
holds the same lease from initial registry lookup until output write/return.

Task1 named tests: symbol_lookup_state_matrix (13 across Ready+Building/Failed,
Failed+Failed; retired+Ready resolves; pending/frozen Failed recognized),
symbol_lease_survives_retire (active counter1->0, names/size retained),
symbol_first_and_launch_share_module and launch_first_and_symbol_share_module
(loads1, queries once per variable/context, stored123 survives),
symbol_late_binding_failure_publishes_nothing and native_binding_span_overflow
(801, no function lookup/returned address; module retained for drain).

Task2 named tests: symbol_combined_error_precedence (direction/unknown; range/failed;
null output/ambiguity), symbol_query_outputs_unchanged, symbol_copy_bounds_and_zero
(offset4/count0 success only for valid symbol; offset3/count2 and overflow1),
symbol_copy_driver_errors (400/709 sticky, ordinary1 recoverable),
symbol_unregister_before_context and symbol_unregister_during_copy (barriers, one
lease, no early unload). Original22 exports remain verified in Runtime26 checks.

Task3 D2D native ownership cases: allocation->symbol, symbol->allocation,
symbol->another-symbol; cross-context global source, stale/unloaded global source,
positive overlap and over-extent must fail without modifying the destination.

Self-review: every spec section maps to Tasks1-4; all five Review Focus cases have
named owner tests. Shared initialization/lease and raw Driver error interfaces above
resolve review gaps before product edits. Scope remains four APIs, scalar u32 only.
