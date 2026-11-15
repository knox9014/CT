# P04b synchronous Runtime symbols over stored u32 globals

Session scope: the user delegated step-by-step implementation and again requested
continuation after the proposed four symbol APIs. The concrete architecture below
is the implementer's choice within the approved CUDA-application compatibility goal.
Retain Rust, app-local same-Driver loading, Intel Arc first, exact staging/privacy.

## Choice and bounded goal

Add cudaGetSymbolAddress, cudaGetSymbolSize, cudaMemcpyToSymbol and
cudaMemcpyFromSymbol to connect unchanged genuine shared-cudart programs to the
existing native u32 storage. Runtime22 becomes additive Runtime26; old22 ABI remains
a verified subset. Driver remains39. No PTX/storage type expansion, new dependency,
UVA/default inference, constants, arrays, async/stream symbol API or device linking.
The other reasonable next steps were broader global types or shared-memory/barriers;
those leave common host symbol imports unresolved and remain separate future work.

## Contract from the pinned original CUDA12 headers

Original cuda_runtime_api.h declares address(void**,const void*),
size(size_t*,const void*), to(const void*,const void*,size_t,size_t,cudaMemcpyKind),
from(void*,const void*,size_t,size_t,cudaMemcpyKind). CUDA error enums are int32.
GetSymbolAddress/GetSymbolSize explicitly preserve outputs on invalid symbol.
This CT slice preserves them on every error and writes only after successful query.
Output null ->1. Host symbol handles are matched as opaque registered host addresses,
never dereferenced or interpreted as legacy strings. Unknown/null/retired/ambiguous
handles ->13 (cudaErrorInvalidSymbol). A known building handle ->13; a known failed
registration preserves its stored error. Failed, unpublished variable metadata does
not create a symbol mapping. Existing first-failure/callback policies stay unchanged.

The scope is version1/flags0/size4 frozen metadata, matching P04a. Unsupported module
eligibility ->801 before Driver use. All four APIs initialize/validate the current
Runtime context and require successful native binding, including size query; no
CPU-only size claim for an unusable module. Missing/foreign optional extension ->35.
Binding failures remain module-scoped sticky, with owned native handle retained.

Copy to allows kind1 (HtoD) and3 (DtoD); from allows2 (DtoH) and3. Kind4 ->801 because
UVA is absent; all wrong/unknown directions ->21. Direction/pointer/range preflight
precedes Driver work. offset+count checked for overflow; range must fit4 bytes.
For count0, null data is allowed and offset0..4 is allowed, but the symbol still
must resolve; no native zero-byte one-past call is issued. Positive count requires
non-null data and nonoverflowing host/device numeric spans. Errors ->1. Positive
D2D overlap retains existing Driver rejection1. No copy error poisons a live module
except existing invalid-handle/destroyed-context failures. TLS last-error behavior
is unchanged: record errors; successful calls do not clear an earlier error.

## Ownership and shared module cache

Registry gains SymbolLease { Arc<RegistrationData>, frozen variable index } with
active-count acquire/drop under the registry lock, analogous to function leases.
Frozen names/size stay owned across unregister. Resolve across live records without
choosing an arbitrary duplicate. Retired mappings are unavailable to new leases;
an already acquired lease may finish once while retire/drain waits.

RegistrationData owns common image/variables/retired access. KernelRuntime.entry
uses registration data/context rather than requiring a function name. Extract one
ensure-module path used by launch and symbol operations. Reserve native binding
records before module load; retain the native module before any global query; store
resolved addresses in frozen variable order. Entry gate covers query/copy and keeps
retirement cleanup out until the active operation ends. Symbol-first then launch,
and launch-first then symbol, must reuse exactly the same module and storage.
Do not add a second loader or module cache. Raw returned address lifetime remains
the caller's responsibility after the API returns; no pointer-generation guarantee.

## Verification and publication

TDD covers stable outputs, opaque lookup, duplicate/retired/failed states, copied
names, per-context identity, symbol-first/launch-first module reuse, bounds/overflow,
zero count/direction precedence, last error, allocation failure before module load,
missing extension, sticky binding failure and unregister blocked inside query/copy.
Use deterministic barriers, no timing sleeps. Preserve all existing tests.

Verify all four signatures against pinned original headers and invoke the actual
Rust DLL through those declarations. Genuine nvcc default-device-runtime/shared
cudart program uses both query APIs and both copy APIs, full/partial copies and
ordinary cudaMemcpy through a returned address. Independent Python owns expected
values, guards and input preservation. Include two contexts, cross-context copy
rejection, explicit retirement control, no-op numerical failure and missing/foreign
provider controls. Existing eight P04a modes and earlier48 cases must remain valid.

Add exactly arc.runtime_symbol_abi and arc.runtime_symbol, retaining all48 IDs
(total50). Bind source/commands/compiler/Cargo outputs/producer/imports/PTX/fatbins,
closed payload roles/raw observations; isolated fresh replay and rehash originals.
Run final fixed candidate in the existing clean validation checkout. Independent
whole-change review then one RED-to-GREEN fix pass, and separate artifact-only audit.
No supported-host/AMD/NVIDIA/framework/release claim. Preserve11 user file hashes,
.gitignore and staged/tracked/history/identity scans; existing draft PR only.

Current runtime-profile limits still contain historical Runtime21/default22/any-var
rejection text despite correct export behavior. Replace those stale limits with the
actual Runtime26 bounded contract as part of profile migration, preserving prior
P04a records as historical evidence rather than rewriting old accepted identities.

## Preimplementation review resolutions

The exported function acquires exactly one SymbolLease, validates eligibility and
passes that same lease through bridge initialization and the gated operation. It
must not copy lib.rs launch's preliminary drop/reacquire pattern. Test unregister
between lookup and ensure_current as well as inside native binding/copy.

Lookup reads pending Record.variables before End and frozen RegistrationData.variables
after End (including a later Failed state). Recorded variables remain recognizable
after later failure; unpublished rejected callbacks do not create mappings. Across
all non-retired records, duplicate host matches yield13 regardless of Ready/Building/
Failed states, including Ready+Building, Ready+Failed and Failed+Failed. Retired+Ready
resolves Ready; two mappings in the same registration follow existing duplicate rules.

Error precedence is CT policy, not claimed NVIDIA parity for combined invalid inputs:
queries: null output1 -> opaque registry lookup/state -> eligibility801 -> current
context/provider -> cached native module/bindings -> success-only output write.
copies: invalid/unsupported direction21/801 -> checked4-byte extent and positive
non-null/nonoverflowing data span1 -> registry lookup/state -> eligibility -> context/
provider/module/binding -> transfer. Zero count still follows lookup/eligibility/native
binding and never issues a native copy. Thus bad direction wins over unknown symbol;
bad range wins over a failed registration; null output wins over ambiguity.

Native transfers call DriverCalls directly, never memory::copy_device (which would
map raw400 to999 too early). A raw400/709 makes the shared entry failed and returns
400/709 for this symbol operation, like kernel operations. Other transfer errors use
existing from_driver and do not poison the module. Ordinary cudaMemcpy mapping is
unchanged. Add positive D2D between global/allocation and two globals; reject foreign
context, retired pointers, overlap and extent crossing using Driver ownership checks.

EntryState.bindings: Vec<Binding{pointer:u64,size:usize}> follows frozen variable order.
Reserve its capacity before load. After any later binding fails, no earlier binding
is published. Validate native pointer nonzero, aligned4, size4 and checked pointer+size
(nonoverflowing) before publication. Cache one load and one query per registered
variable/context. Explicit tests assert symbol-first/launch-first storage continuity.
