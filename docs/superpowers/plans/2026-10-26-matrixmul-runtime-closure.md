# matrixMul Runtime dependency closure

User objective: implement until the currently observed unsupported Runtime imports are removed, report completion, then advance shared memory/barriers. Scope is the eleven imports observed in the pinned matrixMul diagnostic, not every CUDA API or arbitrary CUDA application.

Remaining names: cudaStreamCreateWithFlags; cudaMemcpyAsync; cudaHostAlloc/cudaFreeHost; cudaEventCreate/Destroy/Record/Synchronize/ElapsedTime; cudaProfilerStart/Stop. Stream creation and async copy belong to this list, so they cannot be deferred until after the list is empty. Add cleanup APIs such as cudaStreamDestroy where ownership requires them even if the sample does not import them.

Completion has two distinct gates:
1. Import closure: no missing Runtime import names in the pinned binary; all supported argument paths have real tested behavior, not success stubs. Unsupported flags/stream modes remain explicit bounded exclusions.
2. Application execution: requires shared memory/barriers/FMA and device-selection policy, so zero missing names alone does not pass this gate. Never report matrixMul runnable just because imports resolve.

Dependency order:
A. Owned stream handles: context binding, flags, bounded non-reusing tokens, close/use races, cleanup, ordering policy. Connect created streams to compiler launch configuration, Runtime launch and synchronization. Validate invalid/stale/cross-context handles and current-context preservation.
B. Host allocations: genuine pinned storage via a native API; ownership/extent checks, budgets, double-free rejection, pending-use retention. Do not call pageable malloc pinned allocation.
C. Async submission: owned command data and host lifetimes, per-stream FIFO, delayed errors, synchronization, legacy default/blocking stream ordering. Pointer arguments must never be borrowed from a returned stack. No unmeasured overlap claim.
D. Events: generation-aware record/re-record, completion, destroy-pending safety, timing domain, context checks. Elapsed time must describe real completion and avoid invented GPU timing.
E. Profiler API: documented no-profiler behavior or real CT capture control; never silently pretend to control a GPU profiler.
F. Frozen-source official-header ABI/native fixture tests, fault controls, Runtime/Python/workspace checks; fresh vectorAdd capture/replay and original matrixMul offline diagnostic; independent review and privacy scan. Only report the import gate complete when this evidence passes.

First implementation unit: bounded stream ownership registry and close/submission concurrency tests before public export integration. Keep original user-owned files and old accepted worktrees unchanged. Use separate read-only agents to review architecture and evidence.


## Confirmed implementation priority and comparison hardware

User decision (2026-10-26): finish the defined Intel milestone before starting AMD backend implementation. Intel completion means the agreed supported API/argument scope and real target-application validation, not every CUDA API. AMD remains a subsequent target; keep manufacturer-neutral boundaries where practical without diverting current work to an untested AMD backend.

Use the current Intel machine for development. Before claiming NVIDIA-compatible behavior, arrange access to a CUDA-capable NVIDIA machine for reference execution of the same inputs and CUDA/OS profile. Ownership is unnecessary: borrowed/remote/rented access can supply the reference. Current CT targets Windows x64, so Windows reference runs are needed for matching DLL/API/ABI behavior; Linux numerical results alone do not replace that coverage.

Measure translation overhead by comparing CT with equivalent native execution on the same Intel GPU, controlling algorithm, input, precision, transfers and warmup. A faster/slower NVIDIA GPU is a separate whole-system comparison, not an isolated measure of CT overhead. Acquire AMD validation access when choosing the AMD backend/OS; verify hardware support for that stack before buying. Additional Intel devices are useful later to test generality beyond the current laptop.

## User-value acceptance criteria

User reaffirmed (2026-10-26): prioritize a real CUDA application somebody needs, reproducible setup on another Intel PC, numerical correctness and practically acceptable performance. API/export counts alone do not establish usefulness. Keep source/binary changes minimal where supported, compare existing alternatives before claiming an advantage, and distinguish diagnostic tests from product/framework support. Intel milestone first, AMD afterward.


## Current execution status after Runtime events

The bounded stream, host allocation, queued copy and event dependencies now have
native evidence. Driver46 / Runtime38 are implemented and tested on the current
Intel Windows environment. The original matrixMul still has exactly two missing
Runtime imports: cudaProfilerStart and cudaProfilerStop. The next import task is
the documented profiler-control policy; shared memory/barriers/FMA and device
selection remain independent execution blockers. Do not count import closure as
application execution or universal CUDA completion.

Frozen-source Runtime event capture, original vectorAdd capture/replay and
matrixMul offline inspection are recorded in [Runtime event results](../../RUNTIME-EVENT-RESULTS.md).


## Import-name closure completed

No-collector profiler Start/Stop compatibility is implemented and tested. The
current bounded profile is Driver46 / Runtime40. Original matrixMul schema2
inspection reports zero missing Runtime import names and remains compatibility
unproven; offline PTX still rejects shared memory. It is never launched by the
triage tool. Source-bound native, original vectorAdd capture/replay and independent
review results are in [Profiler import closure results](../../PROFILER-IMPORT-CLOSURE-RESULTS.md).

Import-name closure is complete for this pinned sample. Next work is static
shared memory and uniform block synchronization, then required fused arithmetic
and device selection, followed by actual full-application validation. This is
not universal CUDA completion or a claim of actual profiling capture.

## First uniform barrier slice completed — 2026-10-27

Canonical bar.sync0 now executes in a single returning basic block, with actual
Intel native evidence and exact SPIR-V/validator checks. This does not cover
matrixMul's shared storage or loop barriers. Next implement bounded static shared
storage/addressing/alignment, then prove uniform barrier flow for the required
application before adding fused arithmetic and device selection. Current frozen
capture/replay and offline diagnosis: [barrier results](../../UNIFORM-BLOCK-BARRIER-RESULTS.md).

## Static shared first slice completed — 2026-10-27

Bounded per-kernel static shared arrays and32-bit integer/F32 accesses now have
genuine nvcc/Intel native evidence in a single returning block. A shared pointer
proof rejects space crossing, escapes and uncertain alignment. A narrowing
constant bug found by independent review was reproduced and fixed before capture.
Original vectorAdd capture/replay pass. Original matrixMul remains unexecuted;
its first offline rejection moves from shared line32 to bra.uni line51. Next
prove uniform control flow/loop barrier participation, then required fused
arithmetic/device policy and complete application validation. Details:
[static shared results](../../STATIC-SHARED-MEMORY-RESULTS.md).

## CTA-uniform CFG slice completed — 2026-10-27

CTA-uniform branches/loops with shared memory and barriers have genuine nvcc/Intel
native evidence for finite0/3/5 rounds, plus independent fixed-point/taint reviews,
strict rejection tests and fresh vectorAdd capture/replay. Original matrixMul is
still unexecuted. Its first parser rejection moves from bra.uni line51 to
fma.rn.f32 line86; whole-kernel control proof awaits the parsing dependency.
Next implement numerically validated fused arithmetic and inspect remaining
application/device-selection blockers before full execution. Current evidence:
[uniform control results](../../UNIFORM-CONTROL-FLOW-RESULTS.md).

## Fused F32 and complete offline translation — 2026-10-27

Exact fma.rn.f32 lowers to OpenCL.std fma with bit-oriented native/CPU/integer
oracle evidence; separate multiply/add remains separate. Frozen regression and
original vectorAdd capture/replay pass. Original matrixMul now translates its
complete PTX (2 entries/48 FMA instructions), and schema3 records the translated
module hash without claiming app execution. Separate validator evidence is
bound to the same module. The original app and matrix kernels remain unrun.
Next use small finite original-kernel inputs, numerical/guard/completion checks,
then device-selection policy and full app path validation. Do not equate import
and translation closure with universal CUDA completion. Details:
[fused F32 results](../../FUSED-F32-RESULTS.md).

## Original kernels executed — 2026-10-27

Unchanged original tile16/tile32 PTX now executes through a bounded CT Driver
consumer on Intel B390. Four geometries and two positive seeds verify18944 output
words, all inputs and guards; API-success no-launch/no-copy controls numerically
fail with specific signatures. Fresh-process replay matches positive raw buffers.
Original vectorAdd capture/replay and native parent regressions pass from the same
source. The original matrixMul EXE remains unrun. Source inspection identifies
compute capability attributes75/76 in the explicit-device path; automatic device
ranking additionally asks for multiprocessor count/clock. Next define truthful
virtual-compatibility versus physical-device metadata, then inspect the complete
Runtime/app path with external numeric/finite validation and omission controls.
Evidence: [original kernel results](../../ORIGINAL-MATRIX-KERNEL-RESULTS.md).

## Original EXE Runtime isolation completed — 2026-10-27

The pinned adjusted-build original matrixMul EXE now completes its entire Runtime
path on Intel under an explicitly test-only metadata shim: host allocations,
nonblocking stream, async copies, events,301launches, final copy/sync and frees.
Two small shapes verify7168 finite exact output words; fresh-process replay
matches all buffers/trace/metadata. API-success no-launch/no-HtoD controls expose
the upstream NaN false-PASS and are externally rejected. Fresh parent native,
validator, original vectorAdd capture/replay and original-kernel captures pass.

Production attributes75/76 remain unsupported. The ordinary EXE baseline fails801
before computation; injected5.2/Maxwell text is test data. This does not close
production device selection or establish a full NVIDIA architecture feature set.
Next define and validate that production contract without confusing Intel physical
metadata with NVIDIA SM/clock metrics. Evidence and limitations:
[Runtime isolation results](../../MATRIX-RUNTIME-ISOLATION-RESULTS.md).

## Truthful shared capacity slice completed — 2026-10-27

Driver/Runtime attribute8 now reports min(native Level Zero shared capacity,
CT's authoritative16384-byte static profile). Compiled entries retain aligned
storage budgets; every selected entry is checked against its owning device before
native module creation. Zero capacity, exact boundaries, padding, multiple entries,
no-native-call rejection and native error preservation have regression tests.
Real Intel ABI queries return16384 with unchanged context. Full native parent,
validator, vectorAdd and original matrix-kernel tests pass; metadata-injected
matrix EXE capture and replay also pass for the same source. Product75/76 remains
unsupported. Next review capacity-aware fatbin fallback and define the virtual
target/device-selection contract with explicit unsupported-feature behavior;
neither follows merely from accepting sm52 PTX.
Evidence: [shared capacity results](../../DEVICE-SHARED-CAPACITY-RESULTS.md).

## Capacity-aware candidate selection completed — 2026-10-27

Selection now chooses the highest-ranked fully validated candidate fitting the
owning context device's bounded shared capacity. All candidates still undergo
translation/profile/duplicate/global/ABI checks; no-fit801, metadata/syntax218 and
ordinary native errors remain explicit. Five new selector tests cover order,
aligned/zero/8KiB/16KiB limits and invalid unselected alternatives. Rust204,
Runtime129 and Python219 pass; independent review/clippy/format pass. Fresh native
parent/validator/vectorAdd/original-kernel regressions and injected matrix EXE
capture/replay pass for the same source. Lower-capacity fallback itself is tested
with synthetic limits, not a physical low-capacity GPU.

Next: resolve process-wide Driver/Runtime policy authority and opt-in/default
semantics before implementing a bounded experimental virtual target. The
[reviewed proposal](../specs/2026-10-27-virtual-target-proposal.md) does not yet
change75/76 or product compatibility. Evidence:
[capacity-aware selection results](../../CAPACITY-AWARE-FATBIN-RESULTS.md).

## Actual experimental product virtual target completed — 2026-10-27

Explicit CT_VIRTUAL_TARGET=ct-sm52-subset-v1 now selects virtual CC5.2 through
CT Driver itself, with Runtime delegation and no metadata-injection DLL. Driver
alone latches policy at first valid cuInit(0) attempt before native initialization;
strict/default rejects75/76, invalid configuration is persistent1, nonzero flags
do not latch. Physical Intel identity/native limits, unsupported versions and
SM/clock behavior stay bounded. Runtime CC queries intentionally now use Driver
loading/ordinal/error precedence; documented no-context/output/TLS checks pass.

Rust207/Runtime129/Python224, clippy/format and independent review pass. Fresh
parent native/validator/vectorAdd/original-kernel evidence passes.11 native ABI
cases and8 original matrixMul app cases pass capture/replay. Nominal uses only
the original EXE plus CT Driver/Runtime; traced product runs independently check
7168 finite output words per pass. API-success no-launch/no-copy NaN controls are
rejected externally. Existing ct.py run CLI smoke also completes. This is the
pinned adjusted-build sample and explicit-device experimental scope, not general
CUDA, NVIDIA architecture conformance, AMD, performance or release qualification.
Details: [virtual target results](../../VIRTUAL-TARGET-RESULTS.md).
