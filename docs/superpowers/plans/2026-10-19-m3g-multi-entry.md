# CT M3g / P02 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, TDD for each task, one fresh whole-branch review at the end.

**Goal:** Parse, translate, load and execute several kernels from one PTX/native module.
**Architecture:** shared module parser and SPIR-V writer; native module owns kernel vector;
CUDA function tokens select one entry and its ABI. No new CUDA exports.
**Tech Stack:** existing Rust/Python/MSVC/Level Zero, ignored nvFatbin producer.
**Spec:** [M3g design](../specs/2026-10-19-m3g-multi-entry-design.md).

## Global Constraints

- Base8b73a53; PTX7.0/sm_50 and8.0/sm_52;26 CUDA exports.
- Source256KiB/token65536 per module;1..32 entries; existing per-entry limits unchanged.
- One SPIR-V/native module, no per-kernel substitutions; no used-global/device-call support.
- Full entry-name/ABI-map comparison across alternatives, all validation before native load.
- Kernel destruction precedes native module destruction; failure preserves uncertain resources.
- Native/host pointer trust contract and synchronous1D execution unchanged.
- Vendor/compiled input/raw logs ignored; reviewed staged/history identity checks; draft PR only.

## Review Focus

1. Later entry ignored or scoped names leak: Task1 malformed-second/same-register tests.
2. IDs/signatures/builtin interfaces collide: Task2 binary inspection and Task4 actual native build.
3. Wrong entry ABI reused: Task3 map tests and Task4 mixed-ABI GPU launches.
4. Partial native creation/destruction leaks or retries destroyed handles: Task3 cleanup helper fault test.
5. Stale/foreign handles access another kernel: Task4 unload/context/cross-module tests.

### Task 1: module parser

Files: ct-ptx/src/lib.rs,src/parser.rs; new tests/modules.rs.
Interfaces: pub Module{profile:Profile,kernels:Vec<Kernel>}; parse_module(&str)->Result<Module,Error>.
Legacy parse(&str) wraps it and rejects len!=1 as unsupported.

- [x] Add failing multi-entry/scope, duplicate/global collision, empty/33entry, malformed/unsupported
  second-entry tests; assert source lines, profiles and different ParamKinds per kernel.
- [x] Run cargo test -p ct-ptx, observe RED.
- [x] Refactor header/global parsing once and parse_kernel(&mut Parser,Profile,&BTreeSet<String>).
  Check module token/entry caps and independent entry-local state; reject trailing unknown tokens.
- [x] GREEN all ct-ptx tests; commit parser change.

### Task 2: one multi-entry SPIR-V module

Files: ct-codegen-spirv/src/lib.rs,src/emit.rs; tests/translation.rs.
Interfaces: CompiledEntry{entry:String,params:Vec<Param>};
CompiledModule{profile:Profile,entries:Vec<CompiledEntry>,spirv:Vec<u8>};
translate_module(&str)->Result<CompiledModule,Error>. Legacy translate remains one entry.

- [x] RED tests: two OpEntryPoints/functions with unique IDs, distinct signatures, same
  register names isolated, equal signatures reused, builtin interfaces only per entry.
- [x] Refactor writer to generate multiple functions with global IDs and shared definitions;
  reset function registers/current builtins, cache function types; preserve legacy tests.
- [x] cargo test -p ct-codegen-spirv GREEN; commit codegen change.

### Task 3: candidate selection/native/CUDA ownership

Files: ct-cuda/src/images.rs,src/lib.rs,src/modules.rs; ct-backend-intel/src/lib.rs,src/modules.rs.
Interfaces: compile_candidates -> CompiledModule, identity BTreeMap<String,Vec<ParamKind>>;
OwnedFunction{module:usize,entry:usize}; OwnedModule{native,entries:Vec<CompiledEntry>}.
Backend load_module_entries(c,code,entries:&[&str])->NativeResult<Module> and
launch_entry(c,module,entry:usize,args,grid,block); existing single wrappers preserved.

- [x] RED pure selection tests: alternative entry order/parameter renaming allowed, missing
  entry or ABI change801, unsupported second entry801; metadata mismatch218 still enforced.
- [x] RED cleanup test for destroy_kernel_handles(&mut[usize],FnMut(usize)->NativeResult<()>):
  skip zero; on second destroy failure first is zero, second/third remain; retry never repeats first.
- [x] Implement full-name-map selection; module owns native kernel Vec; validate names/count
  before native creation, retain partial failed handles before cleanup; poison existing failure paths.
- [x] Wire CUDA lookup/launch/unload/context cleanup to module/entry ownership; no new exports.
- [x] workspace tests/rustfmt/Clippy GREEN; commit runtime/backend change.

### Task 4: actual GPU and application integration

Files: new tests/fixtures/multi_entry.ptx,tests/m3g_modules_check.py,
tests/m3g_cuda_app.c,scripts/run_m3g_smoke.ps1,docs/M3g-RESULTS.md; manifest/support docs.

- [x] Build trusted fixture with add/sub four args and scalar-fill(Pointer,F32,U32) three args;
  rename/reorder entries, raw/plain/compressed fatbins via pinned producer.
- [x] Preserved M3f baseline must reject multi-entry source218/801/null before current positive.
- [x] Single module handles execute all entries, including multiple handles for one entry;
  six sizes1/63/64/65/257/50000, CPU oracle/NaN initialization/64 guards.
- [x] Same-name kernels in separate modules must preserve different arithmetic. Test missing500,
  duplicate/invalid later entry218/801/null, foreign handles400, unload invalidation and context
  destruction. Following parse failures the same valid context still computes correctly.
- [x] Independent unchanged C host imports nvcuda.dll, obtains multiple functions from one
  module, launches mixed ABI and verifies guards. Byte-preserving app-local CLI run with
  genuine multi-entry fatbin; classify synthetic host separately from official upstream samples.
- [x] Kernel loop100 and multi-kernel load/unload1000; bounded fault tests, no invalid host pointers.
- [x] Run workspace tests including prepared ignored fixtures/GPU, Python, Clippy/rustfmt,
  check_level_zero_abi.ps1, native M1~M3f; spirv-val if available, otherwise explicit skip.
- [x] Independent whole-branch review; fix findings with RED/GREEN. Publish measured totals,
  update schema1 feature manifest/limits and support docs; privacy/history checks; draft PR
  stacked on M3f, attach it. Main remains unmerged.

## Self-review

Entry indices follow source/native kernel order, while alternative identity uses sorted maps.
Per-entry params and native index travel together in CompiledEntry order. Module teardown
holds all native handles, independent of the number of CUDA function tokens. Parser validates
all entries before any native module exists. Future stored globals belong to P04.

Execution: all four tasks implemented and verified. Measured evidence, review and skipped checks: [M3g results](../../M3g-RESULTS.md).
