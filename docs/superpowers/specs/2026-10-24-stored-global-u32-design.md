# P04a: stored scalar u32 globals through the existing CUDA connection

Status: proposed detailed design. User requested continuation after P09a2-C.
Baseline product258bf92; documentation head df5c242;44 clean required cases passed.
No P04 implementation or new CUDA compatibility is claimed. Main agent implements
inline and independent agents review, preserving the user's selected workflow.

## 1. Goal and bounded scope

Run genuine shared-cudart/default-device-runtime nvcc programs that read/write
module-local scalar u32 globals, using unchanged EXE/fatbin input and the same CT
Runtime/Driver/Intel backend. First acceptance includes initializer, retained value
across launches, two entries sharing storage, host Driver symbol copies, module and
context isolation, reload and explicit retirement/failure paths.

Keep Rust, existing app-local loading, diagnostic nvcc12.0.76/PTX8.0/sm52 recipe,
source/ABI/provenance checks and11 original user-file hashes. Current supported-host
qualification is unavailable. No AMD/NVIDIA execution or full P04/framework/release.

## 2. Approaches and actual preflight

Two mechanisms were considered. A hidden-pointer lowering can use explicit CT-owned
storage but changes internal entry signatures and requires additional packing and
allocation ownership. Native SPIR-V globals preserve current kernel argument ABI;
Intel's backend owns native symbol pointers through its existing module handle.
The common Global IR stays independent of backend handles, so another backend may
implement its own storage strategy later. This does not validate AMD support.

Author recommendation: native exported CrossWorkgroup globals for the first slice.
[Preflight](../../P04a-PREFLIGHT.md) passed the existing OpenCL1.2 validator and actual
Arc native reads7,8,123; stored124; a second identical module remained7 even after
first-module unload. This avoids a speculative internal ABI change. It proves the
native mechanism, not CUDA translation, so all product/native gates remain required.

## 3. PTX/IR and emitted semantics

Accept `.global .align 4 .u32 name` with optional scalar initializer, with optional
`.visible` prefix. Uninitialized supported globals start at zero. Reuse existing
32-bit signed-literal bit rules for initializer values. Total module-global names
remain at most256; identifiers at most128 characters; no duplicate names or entry
collisions. Stored bytes are exactly4 per supported scalar, at most1024/module.

Keep existing unused align8/u64 and bounded b8-array declarations valid but
unsupported for storage/reference/lookup. Preserve their validation and names as
legacy-unsupported metadata. A lookup of a known unsupported declaration returns801;
a genuinely absent name returns500. Used unsupported types reject the module801.
No arrays/constant memory, extern/weak/import/export device-link semantics, relocation,
address-taking, mov-of-global-address or device functions are added. The emitted
SPIR-V Linkage Export is internal host visibility, not CUDA cross-module linking.

Support direct `[symbol]` ld.global.u32/st.global.u32 and their `.volatile` forms
for supported globals, plus the existing register-address instruction forms unchanged.
Only direct symbol accesses are new; no arbitrary symbol expressions/offsets.
Volatile uses SPIR-V Volatile|Aligned (mask3, explicit alignment operand4), never silently omitted and never
presented as atomic/fence/thread synchronization. Concurrent conflicting writes
remain a caller data race; numeric tests use a single writer.

Retain validated stored descriptors in common IR and CompiledModule. Compare all lookup-visible metadata across fatbin candidates: stored descriptors
(name, type, alignment, size, initializer) and known-unsupported symbol names/classes.
Known-unsupported versus absent must also disagree because lookup returns801 versus500.
Legacy unsupported declaration details may differ only when both remain the same
lookup-unsupported class and no storage is observable. Reject disagreement801 before
native work; declaration ordering may differ. Existing entry-signature identity and all decoder/code limits remain.

Emit native globals with OpVariable CrossWorkgroup u32, constant initializer,
Linkage capability and LinkageAttributes Export. Existing user argument signatures
and indices remain unchanged; no hidden parameters. Legacy no-global translation
and parse/translate wrappers preserve existing behavior. Public SPIR-V validation
stays at the existing OpenCL1.2 environment; no target/version bump by implication.

## 4. Native module ownership and global ranges

Extend Backend Module with bounded named pointer/size metadata. Resolve the original
zeModuleGetGlobalPointer only for modules with stored globals. Reserve all ownership
metadata and owned names before native creation. After native module/kernel creation,
query each expected name; require nonnull naturally aligned pointer and size4.
Missing native export is801; descriptor/native symbol disagreement fails closed before
publishing a CUDA module. Preserve first native errors and existing failed-cleanup
retention/poisoning. Query failure triggers existing explicit module cleanup; uncertain
cleanup keeps ownership and never blindly retries.

The native module owns its global memory. Never allocate/free it separately and
never pass its pointers to zeMemFree. Successful module unload removes its named
ranges; failure keeps uncertain native ownership inaccessible through a poisoned
context. Context destroy frees ordinary allocations through the current path and
module-owned globals through module destruction exactly once. No new GPU work in
Drop, TLS destruction or compiler registration callbacks.

Keep user AllocationRanges separate from module-global ranges. Shared range
classification lets current-context copies/fills and pointer arguments use a live
global's exact4-byte extent. Free only accepts ordinary user allocation bases;
cuMemFree(global) returns1 without native free. User allocation behavior is unchanged.
Memory-query APIs on live global pointers return801 without output writes in this
slice; do not fake ordinary allocation base/size or expand CUDA pointer-query parity.
Cross-context/one-past/stale ranges are not accepted for copies. Raw pointer reuse
after unload is a caller lifetime issue, not a promised generational address check.
Module/function handles remain existing opaque monotonic identities.

## 5. Driver ABI and Runtime connection

Driver adds only cuModuleGetGlobal_v2, signature `(CUdeviceptr*,size_t*,CUmodule,const char*)`.
Canonical resolver name cuModuleGetGlobal maps to v2 for verified version3020..12000;
older/out-of-range versions remain rejected. Count39 includes exactly this addition.
Verify the floor/signature with pinned original cudaTypedefs.h and actual typed native
calls before admission. One output may be null; both null is invalid1. Null name is1,
missing/unsupported globals are500/801, invalid module400, and context errors preserve
existing policy. Prepare nonnull outputs safely and never return partial success.
Reset each nonnull writable output to zero first. Error precedence is pinned in
tests: current context, module validity, valid outputs/name, bounded name, then
symbol lookup. One null output is never dereferenced.

Runtime public ABI remains22. Only version1 registrations whose variables all have
the existing ext/constant/global flags0 and size4 become candidates for materialization.
Version2 and other variable metadata remain801 before bridge use. Constructors remain
CPU-only. Freeze variable bindings at successful End into RegistrationData, so leases
and native cache ownership retain names/sizes through concurrent unregister. Live
mapping capacity is released on retire while retained metadata stays bounded by
existing token/native-record/image limits. Failed/post-End/retired precedence stays.

On a variable-bearing first launch, lazily resolve cuModuleGetGlobal_v2 from the same
pinned Driver, separately from the old five kernel symbols. Missing/foreign global
extension35 must not disable memory or no-variable launches. Load the actual module,
publish its handle in ownership state before further calls, then verify every
registered variable name/size against Driver metadata before function lookup/launch.
Missing/unsupported/mismatched variables become a sticky801 for that module key;
retain the native handle for existing explicit cleanup. Existing per-function lookup
errors, leases, per-context caches and retire/drain rules stay intact. No vendor-name
exception, no copied host-variable initial data, no duplicate Driver state.

No cudaGetSymbolAddress/Size/ToSymbol/FromSymbol APIs are added yet. A direct Driver
consumer uses GetGlobal plus existing copies; the genuine Runtime consumer reads and
writes globals through its compiled kernels. Both use the same actual storage.

## 6. Existing gates and new evidence

Retain all44 current IDs and semantics except explicitly superseded rejection inputs.
The historical C used-u32 rejection source/EXE remains historical evidence; it cannot
be claimed to become a successful unchanged application because its host asserts801.
Keep that source unchanged. Switch the current C rejection fixture to a separately
named actual-used volatile u64 global that remains outside this slice; bind the new
source/EXE/PTX/imports explicitly. Retain genuine positive programs, zero-additional-
Driver-call controls, no-op numeric rejection and all ABI subsets. Adjust the old
manual control's unsupported variable size8 proof only as documented; a new P04
positive explicitly proves supported unused-u32 metadata does not poison a module.

Use independently checked guarded outputs and preserved inputs, initializer zero/
nonzero,100 repeated kernel calls and1000 scalar module load/unload cycles as bounded
regressions, not reliability guarantees. Validate fresh generated SPIR-V with pinned
spirv-val, then execute unchanged genuine nvcc programs through Runtime22/Driver39
on Arc. Verify two globals/two entries share state, sibling untouched values,
same-name globals across modules, two contexts, unload/reload reset and retired token
behavior. Add native host GetGlobal size-only/address-only/error cases and copy/free/
query extents. Use randomized host mutations and independently computed arithmetic.

Fault injection must cover partial module/global query and cleanup, size/alignment/
range overlap, host metadata allocation before native work, failed copy, and unregister
while validation is blocked. Invalid global code/metadata cannot become a successful
kernel. Missing/forwarded global extension remains35 in typed controls. Capture
rebuilt artifact identities, fresh seeds, full arrays/guards, positive and negative
controls, then independently reconstruct the fixed clean bundle.

Proposed additions: validator.global_u32, arc.global_abi, arc.global_driver and
arc.runtime_global. These are planned IDs, not passing tests. All44 previous IDs must
remain; actual configuration determines the required count. Add exact source/config/
profile/tool evidence roles and stale-pointer protection, preserving closed schemas.

## 7. Work boundaries and decision ownership

Implementation order: typed stored globals/volatile parser and IR; SPIR-V emission
and validator; backend global metadata/ownership; Driver39 and range operations;
Runtime bindings and lazy same-Driver extension; native fixtures/evidence and C
rejection migration; fixed clean gates, independent review/audit and privacy scans.
Main-agent inline implementation remains selected. All detailed bounds, first scalar
type and native mechanism above are author proposals for review, not new completed
capabilities. Full linking, constants, larger types/arrays, symbol Runtime APIs,
parallel atomics and another backend need separate designs and actual tests.

## 8. Builder check resolution

The independent builder check identified one observable-identity gap: legacy
unsupported globals also distinguish lookup801 from missing500. Author decision:
compare those symbol names/classes across candidates as well as complete stored
u32 descriptors; reject disagreement before native work. This preserves observable
lookup consistency while allowing irrelevant unsupported initializer/type details
to vary within the same rejected class. No question requiring a new user preference
remains; fresh implementation and native evidence are still required.
