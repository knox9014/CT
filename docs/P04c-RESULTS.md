# P04c scalar u64 globals: verified Arc diagnostic preview

2026-10-25. The native storage path now supports both scalar u32 and u64 globals.
Runtime26 and Driver39 exports are unchanged. No general CUDA or release claim.

## Clean acceptance identity

The fixed candidate passed **52/52 required combined cases**:0 failed,0 skipped,
0 not-run, errors=[]. All old50 IDs remain, with exactly validator.global_u64 and
arc.runtime_global_u64 added. These are bounded correctness/ABI/control cases,
not a count of supported external applications. Rust137, Runtime77, Python152 and
fmt/clippy passed again; combined Rust enabled the three ignored tests (140 total).

- Tested code: `5e2b302feb3b75d327710c95fc0c7cf574efe289`.
- Clean source fingerprint: `14f08604a1d6120d867c3eb6a6b1752606537c52104b89fbaeedf964d5b329ad`.
- Source clean:true, release_claim:false; GPU Intel(R) Arc(TM) B390 GPU.
- Report SHA256: `b3933abbc5b7b36243671de11d3d3f55fb09562f1bed67b4b9fea9e10db1e72d`.
- Configuration SHA256: `438198e7367496b14d4460d2ca1721182af49c1f8e021bb90b0efbc0364bc452`.
- Toolchain file SHA256: `dcf614230dfee457bea5e8851b05ab28e35fce09cf2b8c34affc2b074a3f8e96`.
- U64 native manifest SHA256: `ddaafe690d80e2b2465b463e3dcce9a2486f3b99da82c9ee341a564c3dde0aa3`.
- Genuine nvcc host EXE SHA256: `c2479af71bdbd97bbfb3be90626755d777cae6f06e0fbdb128ad90022f3ec168`.
- Driver DLL SHA256: `a814e7eec1535417e90f1a65cf595865c92aef3b2458df113ad23399785aa53a`.
- Runtime DLL SHA256: `23f6c75bda48751009a07add4ec45618a63e9aefdd9c80f7f51ac42907b4fc9f`.

Base/default CUDA producers were freshly rebuilt in the new clean checkout using
unchanged pinned archives/tools; all current native fixtures/controls were rebuilt
and revalidated/replayed. Preserved baseline DLL gates retain their explicit
source-revision-unverified provenance. Source and bundle identities are independent
of later result-only documentation commits. Retained execution data stays under
`results/local/p04c-clean-5e2b302/` in the managed acceptance checkout.

## Contract

PTX align4/u32 and align8/u64 globals retain full initializer bits and direct typed
ordinary/volatile kernel accesses. Host symbol queries/copies and launches use one
context-owned module and native storage. Mixed modules validate each native size,
alignment, nonoverflowing extent and nonoverlap. Runtime registration remains
version1/flags0; other metadata/types remain unsupported.

Copies enforce each symbol's4/8-byte bound, including partial byte transfers and
zero count. Lookup failures retain the legacy4-byte combined-error bound; unknown
or retired handles at offset8/count0 return1, while offset4/count0 returns13.
Queries preserve outputs on errors. Lease/retirement, cleanup ownership and sticky
raw400/709 behavior are unchanged. This is a CT precedence policy, not NVIDIA
parity for all combinations of invalid arguments.

## Actual verification

Root development checkout: Rust137, standalone Runtime77, Python152, fmt/clippy and
profiles/coverage passed. SPIR-V validated four positive modules and rejected two
corrupt controls. Genuine nvcc host execution passed eight modes and isolated
fresh-seed replay. These working-checkout diagnostics are distinct from clean
acceptance below.

The fixture exercises two contexts,100 updates each, guarded17-value output,
high32-bit initial values, explicit64-bit wraparound, guarded partial reads and
writes, D2D directions, mixed-width state, stale/foreign/overlapping extents and
retirement. Native controls query a separately owned Driver module and verify its
independent4/8-byte initialized storage, while Driver copies use Runtime-queried
addresses on the Runtime storage. No executable/PTX bytes are patched.

The old unsupported-u64 input is now an actual-used aligned16-byte volatile array.
Current P04a/default Runtime controls must still reject it with exact801. Compiler
PTX, size16 registration, source/recipes, Cargo outputs and raw observations are
bound to current evidence; historical accepted artifacts remain unchanged.

## Scope decisions

nvcc can fold a u32 load into a b64 register, and generic inferred-pointer64-bit
memory requires stronger explicit alignment than ordinary nvcc parameter metadata.
Those broader grammar/ABI changes remain outside this slice. The positive fixture
uses guarded u32 output derived from both halves of the u64 values, plus full64-bit
host snapshots and separate u32 updates in the same module. Named aligned globals
no longer incorrectly raise unrelated32-bit pointer parameter alignment; a targeted
regression test protects this distinction while existing weak64-bit-pointer memory
rejection stays intact.

The dedicated u64 runner/evidence follows the established P04b closure structure,
reusing producer/Cargo/bundle helpers. This keeps profile identities separate but
has some duplicated validation maintenance. No actionable findings were returned
by the independent whole-change source review of b7511bc..fe46b9a.

Raw logs/vendor binaries/local paths remain local and ignored. Existing11 user
files are preserved. AMD/NVIDIA, other OS/GPU/compiler qualification, arrays,
constants, async/streams, atomics, device linking, arbitrary apps/AI frameworks,
performance and hostile-program isolation remain unqualified.

## Validation-control correction

The first clean fe46b9a run passed47/52, including both new u64 gates, but was not
accepted. Old rejection controls still treated an eight-byte registration or an
unused u64 declaration as unsupported. The validation-only fix pass migrated the
remaining pure Runtime ABI/default control to size16 and Driver legacy metadata to
an unsupported b8[16] declaration, retaining exact rejection assertions. Targeted
original-header ABI/default nvcc/no-op and direct Driver1000-module checks passed.
Product implementation remains the independently reviewed fe46b9a code; the final
candidate adds these three control-source changes. Historical failed/accepted
reports and vendor artifacts were preserved rather than relabeled.

## Independent artifact audit

The separate guarded read-only audit completed reconstruction with errors=[]. It
verified the independent pinned execution lock, all52 passes and the exact old50
IDs plus the two u64 gates. HEAD, logical clean state and live source fingerprint
were unchanged before/after. It rehashed8,556 unique audit-read files (2,553 under
the accepted checkout including71 bundle files,6,003 external dependencies), with
zero changes. Only20 Git read commands were permitted; compiler/native payload,
GPU/replay execution and file mutation were blocked during the successful audit.
This coverage describes the files actually read, not every file on the machine;
Git index metadata identity is not claimed.

The independent audit produced its complete structured report, which the main
agent checked against the recorded identities and audit protocol. Its source
review and artifact reconstruction are distinct from the earlier actual native
fresh-seed replay in the required lane. No merge or release is authorized by them.
