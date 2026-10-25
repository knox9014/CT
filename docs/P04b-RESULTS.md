# P04b synchronous Runtime symbols: verified Arc preview

2026-10-24: the fixed code candidate passed **50/50 required combined cases** in
the clean validation checkout:0 failed,0 skipped,0 not-run, errors=[]. The lane
retained all48 existing IDs and added exactly `arc.runtime_symbol_abi` and
`arc.runtime_symbol`. Cases include positive workloads and rejection controls;
50 is not a count of supported applications. No merge or release is claimed.

## Exact tested identity

- Native-tested code: `6003b37ccc162c89041bb987c42948bf219c612d`.
- Live source fingerprint: `bf82da62f4d32fefced70547c787d2d2df888265c1491d33f0fa3bc7a2c12939`.
- Source clean:true; release_claim:false.
- Observed GPU: Intel(R) Arc(TM) B390 GPU.
- Report SHA256: `ca66d77414574603580d492a107fb69ed843d96f68e73ab1caff7869b8d1f713`.
- Configuration SHA256: `7750fe26b8d3063f46a6ddf37640d0668aa8eb8476ef2a1062cd6ad5dc1e8976`.
- Toolchain file SHA256: `dcf614230dfee457bea5e8851b05ab28e35fce09cf2b8c34affc2b074a3f8e96`.
- Symbol native manifest SHA256: `f1ae2913189d93aaa50b1d30db57ecff687a3462f29c50ae145c804115a07ab7`.
- Symbol ABI manifest SHA256: `c1f1c529ee87d9da988b22801e40f598e04250743d8f9513319ee3bb96035e32`.

| Native symbol lane artifact | SHA256 |
| --- | --- |
| Genuine nvcc host EXE | 488bd546ced8b0c77657a6087f3e0ad5c0c722bf2a32597b6105be81a560b19c |
| CT Driver DLL | 272caee903e4d94e1e529f03a005b8416718650d3812333c0794a1dc5f2506f8 |
| CT Runtime DLL | 53e90e189d6a9d72de49fd7e621554f797e7b22e9afe4136b9d2f8177131d848 |

The ABI lane rebuilds its own copies from the same candidate; its manifest binds
those separate binaries and compiler recipes. Later result-only documentation does
not change the code tested above. Local evidence remains under
`results/local/p04b-clean-6003b37/` in the managed validation checkout. Vendor
headers/binaries, raw logs, local paths and execution bundles are not published.

## Implemented contract

Runtime22 becomes additive Runtime26; Driver remains39. The four added exports are
`cudaGetSymbolAddress`, `cudaGetSymbolSize`, `cudaMemcpyToSymbol` and
`cudaMemcpyFromSymbol`. Existing14/21/22 declarations and typed calls remain checked;
current native consumers assert exact26 exports and exercise the new calls.

Version1/flags0/size4 stored scalar u32 metadata only. Opaque host symbol addresses
resolve against frozen owned registration data; null/unknown/retired/ambiguous
symbols return13. Failed known registrations preserve their recorded error. Queries
write outputs only on success and require native binding, including size query.

A single SymbolLease survives provider initialization, native binding/copy and query
output publication. Launch and symbol operations share one context-keyed module,
immutable binding order and entry gate; symbol-first and launch-first orders retain
the same storage. Binding failure is sticky and never publishes earlier partial
bindings; native handles remain owned for retirement. Span/alignment/size checks
precede exposure. Unregister prevents new leases while an existing operation may
finish once; explicit matching-context drain reclaims after active operations end.

ToSymbol accepts HtoD/DtoD, FromSymbol accepts DtoH/DtoD. Direction/range preflight
uses checked offset+count<=4. Zero count still resolves the symbol, allows null data
and offset4, and performs no native copy. Default/UVA returns801; wrong direction21;
bad spans1. Raw copy400/709 poisons the shared entry without losing the native error.
Ordinary invalid-value copy errors remain recoverable; existing cudaMemcpy mapping
is unchanged. Combined-invalid-input precedence is explicit CT policy, not a claim
of general NVIDIA behavior. See the linked design for its exact ordering.

## Executed verification

The clean lane passed root Rust132 tests, standalone Runtime74 tests, Python139
tests, root/Runtime fmt and all-target clippy with denied warnings. The final combined
Rust case also enabled the three previously ignored native/producer tests (135 total).
Pinned original headers, actual SPIRV-Tools and the full earlier48-case lane passed.
Previously pinned base producers were reused and revalidated/replayed; the current
P04b CUDA fixtures, controls and CT DLLs were rebuilt during this lane.

The original CUDA12 headers compile all four exact function-pointer types and enum
sizes/values. A native consumer calls the actual Rust DLL using those declarations,
checks exact26 exports, output preservation, errors and GPU-free preflight with no
adjacent Driver. Diagnostic nvcc uses default device-runtime/shared-cudart settings,
without `--cudadevrt=none`; its compiled EXE is executed unchanged through CT.

Eight native modes passed: symbol-first, launch-first, a fresh positive seed for
each order, exact numerical no-op, explicit retirement, missing extension and
foreign-owned extension. Positive programs use two contexts,100 read/update cycles
per context,17 output values,64 guards on each side, preserved input arrays and
context revisit. They check partial ToSymbol writes, full FromSymbol reads,
queried-address ordinary memcpy, allocation-to-global/global-to-allocation and
global-to-global D2D. Foreign/stale allocation/stale global/overlap/extent operations
must fail without changing the observed final state. Manual retirement removes new
symbol lookup and drains the native module; the old address is then rejected.

Independent Python owns expected values, masks, guards, input/state/sequence and
context isolation. No-op is accepted only for its exact suppressed-kernel results
with intact inputs/guards, not an arbitrary mismatch. Closed schemas bind actual
producer/compiler recipes, Cargo DLL outputs, source/headers, PTX/fatbin/stub and
default dlink output, fixed payload roles and raw stdout/stderr. Capture requires
isolated new-seed replay and rehashes original artifacts afterward. Unit controls
reject schema/status forgery, stale pointers, altered recipes/inputs, rehashed DLL
substitution against retained Cargo output, raw observations and no-op corruption.
These are trusted local build/evidence checks, not authentication of arbitrary
externally submitted executables.

## Independent review and remaining coverage

One fresh-context whole-change review of99fc330..6003b37 found no Critical or
Important defects. One P3 test-coverage suggestion is retained: positive native
FromSymbol calls currently use4 bytes/offset0. Rust fake-driver tests cover partial
FromSymbol offsets/counts; an actual two-byte read at offset1 into a guarded host
buffer is not yet qualified. This is not an observed product defect, and native
partial-read byte selection/host-guard coverage is not claimed. No second product
source review or fix pass was needed.

Independent read-only artifact reconstruction returned errors=[] and verified the
pinned old execution lock, all50 passes and exact old48/+2 case identity. HEAD, clean
state and live source fingerprint were unchanged before/after. It rehashed8,408
unique audit-read files, including68 result files and2,078 cache files (the remainder
source/tool dependencies), with zero changes. No compiler/native/GPU/replay execution
was performed during this audit; actual fresh native replay occurred in the required
lane. Initial Git status calls could refresh index metadata, so unchanged index
metadata is not claimed; source/artifact bytes and logical clean state are verified.

## Rulings and limits

1. Reuse the existing feature checkout with exact staging and11 preserved user
   files, plus the externally managed clean validation checkout. No merge/release
   or cleanup of retained acceptance evidence. Keep an ignored execution ledger
   and RED/GREEN logs for traceability; no Bash-only helper dependency.
2. Commit Tasks1/2 together: Task1's new internal symbol path is unused until the
   four public adapters consume it. This avoids temporary production lint bypasses;
   separate RED/GREEN contracts still ran before the coherent Runtime commit.
3. Migrate old exact22 native export checks to exact26 while preserving every old
   typed load/call and adding new typed preflight. Old ABI observations remain
   subset records, not relabeled full Runtime26 ABI proof.
4. Fix stale Runtime21/default22/any-variable rejection text in current profile and
   coverage registries. Preserve P04a historical candidate/result records unchanged.
5. Keep the reviewed P3 native partial FromSymbol test as explicit follow-up rather
   than silently claiming that coverage or expanding the accepted scope.

This is a Windows x64/Intel Arc diagnostic preview with the MSVC override. It does
not qualify a supported host compiler, AMD/NVIDIA execution, arbitrary CUDA apps,
AI frameworks, arrays/constants/wider global types, UVA, async/streams, atomics,
general device linking, hostile-program isolation, performance or a release.

Design: [synchronous Runtime symbols](superpowers/specs/2026-10-24-runtime-symbol-design.md).
Plan: [P04b implementation](superpowers/plans/2026-10-24-runtime-symbol.md).
