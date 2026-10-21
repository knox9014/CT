# P06a first slice: device copy and typed fill

Verified 2026-10-21, Windows x64 / Intel Arc B390.
Clean native-tested candidate: `6fc988775ae5881309bc4e7499683d7a7885d026`.
Execution-scope SHA-256:
`15de0f0dbf26d1aa41212e20ddcf60a5aae03a8c9ea7030c922724bb76a61a01`.
Subsequent documentation commits do not relabel this native candidate.

## Implemented behavior

CT now exports `cuMemcpyDtoD_v2`, `cuMemsetD8_v2`, `cuMemsetD16_v2` and
`cuMemsetD32_v2`, bringing the total to36. All four use the official v3020
Windows x64 ABI and canonical lookup names within the existing12000 ceiling.
This is a partial P06a result: pointer property/address-range queries remain.

D2D submits a direct Level Zero device copy without host staging. Both spans
must belong to the current context and fit individual allocations. Nonoverlapping
regions within one allocation are supported; positive overlap, including identical
pointers, is rejected as a CT profile restriction. Typed fill repeats the complete
1/2/4-byte value with checked element-count multiplication and alignment.

Selected queue pattern-size capability is checked before submitting a positive
fill. An unsupported width returns801 without poisoning. Uncertain append failure
poisons the context and retains owned pattern storage and resources. Successful
synchronous completion releases the pattern. Zero operations require valid
owned interior addresses, typed alignment and a usable current context.
See the precise [Driver contract](compatibility/driver-api.md) and
[lookup floors](compatibility/driver-entrypoints.md).

## Observed validation

| Gate | Result |
| --- | --- |
| Clean required combined cases | 31/31 passed; release_claim=false |
| Rust | 101 normal;103 including prepared cases |
| Python | 62 passed |
| Official CUDA header ABI | 36 signatures and official-PFN calls passed |
| New unchanged native consumer | 55 cases,58,880 checked bytes,23 rejected requests |
| Existing Arc/consumer regression | All required cases passed |
| Producer and actual SPIR-V controls | All required cases passed |
| Independent bundle audit | Clean source/config/environment/catalog/tool/input identities matched |

The CT-owned native app includes only official CUDA declarations and runs inside
an application-local driver bundle without byte changes. It checks odd sizes,
interior offsets, adjacent regions, zero/all-one/multibyte fill values, full source
preservation and destination guards, overflow, alignment, overlap, foreign-context
and freed addresses, no-current/init errors and lookup version/flag boundaries.

RED evidence: the prior resolver rejected the new canonical names, backend tests
lacked the new methods, and the native consumer reported missing memory exports.
A preserved older local DLL SHA-256
`97b66eee0902c4c9a34a449ddb33a06d2123494a5e1a048909bd764f259658ae`
was subsequently rejected for missing exports. This is artifact negative-control
evidence, not an independently reconstructed baseline build.

An initial native zero-span assertion incorrectly assumed an allocation's end
could never begin another valid allocation. The GPU allocator produced adjacent
ranges. The test now uses an address outside both allocations; production range
policy was unchanged. CPU range tests retain explicit unowned-end cases.

Two independent read-only reviews covered the contract and implementation.
The queue capability check and conservative pattern lifetime were incorporated;
final review reported no material finding in inspected paths. Synthetic backend
tests validate failure poisoning, retained patterns, no subsequent submission or
cleanup, and nonpoisoning capability rejection. They do not establish physical
device failure behavior. Publication/identity checks passed; all11 saved original
user files retain their hashes and remain outside these commits. Raw reports,
headers and generated binaries stay ignored. Hosted CPU/validator CI is recorded
separately on the stacked draft PR.

## Limits and next inputs

CT serializes calls and waits for completion. CUDA's host-asynchronous behavior,
default-stream concurrency, PTDS, async exports and performance parity are not
established. See [CUDA synchronization rules](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-driver-api/api-sync-behavior.html).
Zero-count pointer and overlap rejection are documented CT guards; exact NVIDIA
error parity remains unverified. Native raw addresses may be reused after free.
No generation-safe pointer or cross-context/peer/UVA support is implied.

Next is the remaining P06a allocation/pointer property query contract. P05
nondefault scheduling, pinned/managed/2D/3D memory, general Runtime/framework/
external libraries and AMD/NVIDIA GPU execution remain outstanding. These
tests do not establish universal CUDA compatibility or a release.

The subsequent [query slice](P06a-QUERY-RESULTS.md) now records bounded allocation
range and four pointer attributes; it preserves the remaining UVA restrictions.
