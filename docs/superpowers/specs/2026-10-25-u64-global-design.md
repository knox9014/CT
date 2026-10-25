# P04c: scalar u64 globals through CUDA Driver and Runtime

Status: user approved this design on 2026-10-25 ("가자"); implemented at candidate5e2b302 with clean required52/52 pass; see [results](../../P04c-RESULTS.md).
Baseline: 7bffe16. On 2026-10-25 the user selected 64-bit global-variable support
instead of shared memory/block synchronization. The detailed choices below are
the implementer's proposals, not additional user decisions.

## Goal and approaches

Run unchanged genuine nvcc shared-cudart programs using both scalar u32 and u64
device globals on the existing Intel Arc path. The same global must be visible
to kernel loads/stores, Driver global queries/copies and all four Runtime symbol
APIs. Preserve Rust, app-local loading, current module/context lifetime contracts,
privacy checks and explicit unsupported behavior.

Chosen direction: extend the existing typed storage/owned-module path end to end.
A host-only eight-byte symbol API is insufficient: kernels must observe the same
native storage. A separate u64-only module/cache would break mixed-width modules
and ownership, so it is rejected. Shared-memory/barrier support was considered as
the alternative next feature; the user selected u64 globals first.

No new CUDA exports, dependencies or OS/backend are required. Runtime remains26,
Driver39. This slice does not add signed/bit aliases for named globals, float
globals, arrays/constants/externs, device linking, arbitrary global addresses,
atomics, shared memory, streams, async copies, UVA or framework compatibility.

## PTX and code generation contract

Keep MutableU32 unchanged and add MutableU64 { initializer: u64 } to GlobalStorage.
Central accessors provide supported storage type, byte size and alignment, avoiding
independent hardcoded width rules in consumers. Unsupported remains explicit.

Accept scalar `.global .align 8 .u64 name` with existing optional visibility,
zero initialization or a single initializer handled by the existing U64 scalar
literal semantics. Test zero, nonzero high32 bits, u64::MAX/negative-one bits and
malformed/overflow literals; do not expand constant-expression grammar. Maximum
256 globals and existing identifier/name collision limits stay unchanged.

Permit ordinary/volatile ld.global.u64 and st.global.u64 to the matching named
u64 global, with no offset/address-taking or mixed-width reinterpretation. Keep
u32 typed accesses unchanged. Reject mismatched widths and unsupported modifiers.
Existing register/address-based U64 operations keep their current semantics.

Emit the matching SPIR-V global pointer/type and full64-bit initializer. Keep
Linkage Export plus HostAccessINTEL ReadWrite annotations so unused-by-kernel
symbols remain host-observable. Mixed widths and multiple entries share the same
owned global table. Validate generated SPIR-V with the pinned validator before
native execution. No software/CPU fallback or hardcoded workload substitution.

## Driver/backend binding and lifetime

Pass each supported global's expected byte size (4 or8) from the compiled module
to the Intel backend; do not silently filter u64 out. Native pointer lookup must
return exactly the expected size, a nonzero pointer aligned to that width and a
nonoverflowing pointer+size extent. Different globals may not overlap; mixed
4/8-byte modules use their individual extents for that check.

Preserve ownership before lookup, failure cleanup/retention, context ownership,
global versus allocation address validation and unload rejection. Driver queries
report the actual validated size. Raw copy remains byte-oriented; legal partial
host transfers need not have width alignment beyond the existing copy contracts.
No shared entry is published with a subset of its required global bindings.

## Runtime registration and symbol contracts

Version1, zero external/constant/global flags, and scalar size4 or8 metadata become
eligible. Metadata size alone does not prove the PTX type: module compilation and
native binding must also agree. Unsupported array or type contents remain801.
Successful bindings match each variable's registered size and width alignment.
Use one SymbolLease across lookup, initialization, action and output publication,
with the existing context-keyed cache and entry gate for launches and symbols.

Queries preserve output on every failure. Null output1; invalid/ambiguous/retired
symbol13; recorded registration failure and native error mappings stay unchanged.
GetSymbolSize requires native resolution and returns4 or8, not metadata alone.

Copies keep To HtoD/DtoD and From DtoH/DtoD; Default801, wrong direction21.
The following staged range policy preserves old four-byte rejection behavior:

1. Direction, checked offset+count overflow, null nonempty data and host-address
   span overflow are rejected before any registry/provider work (existing codes).
2. Compute the logical symbol lookup without initializing a provider. If lookup
   fails, apply the old four-byte range check before returning that lookup error:
   an end>4 returns1; otherwise return its original lookup error. Thus unknown,
   ambiguous, building and failed handles retain their old combined-error policy.
3. With a valid lease, use its registered size only when it is4 or8; otherwise use
   the old4-byte bound. Reject end>bound with1 before module eligibility/provider
   work. A valid8-byte symbol therefore accepts offsets/counts through8; a4-byte
   symbol still rejects end>4, even in a mixed module.
4. Check image eligibility, provider/context and all native bindings, then copy.
   Successful binding size must match metadata, as above. No metadata-only copy.

This is explicit CT precedence, not a claim of NVIDIA parity for combined invalid
arguments. Test these stages directly with fake drivers, including zero-count
offset4/8, offset beyond the width, unknown/ambiguous/failed handles and invalid
module metadata. Count0 still resolves native storage and performs no native copy.
Raw400/709 still fails the shared entry; ordinary invalid-value1 is recoverable.
Retirement/drain/concurrent-operation guarantees are unchanged.

## Negative fixture and evidence migration

The current default_unsupported_global.cu intentionally uses scalar u64 and asserts
801. It must no longer serve as the unsupported control after this feature.
Replace its current source behavior with an explicitly 8-byte-aligned volatile
unsigned-char array of16 bytes and an actual-used load. Arrays/u8 loads remain
unsupported in this slice. Keep the fixture path and observable mode/error schema
so existing gate IDs can be retained. Assert actual generated `.b8` array storage,
registration size16 and volatile load: neither an optimized-away symbol nor an
unrelated compiler/load failure qualifies as this negative control.

Update validators which bind negative source/metadata expectations, rebuild every
affected current producer/consumer and regenerate their evidence in new ignored
directories. Freeze/pin new current producer/configuration identities before the
final lane; do not reuse mismatched old artifact hashes. If an existing producer
script has a fixed output directory, use an isolated clean validation checkout
with its own cache, preserving the historical checkout/cache. Keep old accepted
source commits, manifests, clean50 reports and P04a/P04b results unchanged.

Add a separate genuine u64-positive fixture rather than relabeling an old negative
manifest as a pass. Both current P04a/default-runtime negative gates must still
observe exact801 with no output mutation where applicable. Retain prior u32
positive, no-op, retirement and provider-control coverage.

## Verification and completion

- Rust parser/IR/codegen tests: mixed widths/entries, exact initializer bits,
  ordinary/volatile typed accesses, mismatches, limits and unsupported arrays.
- Backend/fake-driver tests: size4/8 mismatch, null/misaligned/overflowing/overlapping
  native pointers, partial binding failure and cleanup, context/unload ownership.
- Runtime tests: mixed metadata sizes, query output preservation, per-symbol
  ranges, staged error precedence, zero count, sticky errors and retirement races.
- Genuine nvcc default-device-runtime/shared-cudart host, unchanged after build:
  two contexts, symbol-first and launch-first, repeated kernel writes and host
  reads/writes, mixed u32/u64 globals and Driver/Runtime shared storage.
- Use deterministic upper32-bit patterns, wrap boundaries and byte-wise partial
  reads/writes with both-side guards. Independently compute expected Python values;
  include D2D all relevant directions, exact no-op controls and fresh-seed replay.
- Preserve existing50 required gate IDs; add a distinct u64 semantic/SPIR-V gate
  and a native u64 integration gate, targeting52 required cases. Existing gates
  migrate their unsupported input deliberately as above; no silent case removal.
- Run Rust/Python suites, fmt/clippy, original-header ABI checks, all required
  lanes and independent review on a fixed candidate. A full clean acceptance report
  is separate from exploratory dirty-checkout smoke results.

Raw logs/vendor binaries/local paths stay ignored; public records contain only
sanitized results and exact tested identities. Preserve the11 user files. Keep
the existing draft PR workflow; no merge/release or historical evidence cleanup.
Other hardware, general CUDA compatibility and performance remain unqualified.

Builder may choose test helper factoring, fixture kernel/function names and commit
boundaries. New API/type/synchronization scope or weakened old error/ownership
contracts require returning to the design. Detailed implementation plan follows
design approval.

## Independent builder check

2026-10-25: a fresh read-only reviewer inspected this design and relevant source,
reporting "nothing important left". Mixed-width range/error precedence and the
negative producer migration were explicitly considered. No product/GPU execution
was performed for this design review. The user subsequently approved this design.
