# P05a primary context design

## Intent and approved scope

Continue the approved universal CUDA plan with a usable shared primary context
for existing Driver consumers. Preserve Rust, process-local loading, existing
user changes, and privacy-safe publication. This slice implements P05a, not all
of P05 or Runtime compatibility.

## Contract

- Export `cuDevicePrimaryCtxRetain`, `cuDevicePrimaryCtxGetState`, and
  `cuDevicePrimaryCtxRelease_v2`. Canonical resolver floors are 7000, 7000,
  and 11000 respectively, with the existing 12000 lookup ceiling. No legacy
  release alias, reset, or set-flags pointer is advertised.
- A device has one active primary handle while its checked reference count is
  positive. Retain creates lazily; failed creation leaves no reference. Ordinary
  contexts remain separate. GetState observes without creating a native context;
  flags are zero in this default-flags-only slice.
- Retain and release do not change TLS. Existing set/push/pop calls select the
  shared context per thread. A second consumer can use its allocations/modules.
- The last release invalidates the handle and all owned resources, using the
  existing ordered native cleanup and failure quarantine. A subsequent retain
  gets a fresh monotonic handle. Failed cleanup returns its error and is never
  retried or reactivated through the old handle.
- Released primary handles remain tombstoned. Operations on a stale primary
  context report 709 (`CUDA_ERROR_CONTEXT_IS_DESTROYED`), including a stale TLS
  top; output handles are cleared. TLS is not implicitly popped. This is CT's
  deterministic stale-handle policy, not measured NVIDIA parity after release.
- `cuCtxDestroy_v2` rejects an active primary handle with 201 and leaves its
  references, resources, and TLS intact. This is an explicit CT guard; the
  exact NVIDIA error for that invalid usage has not been hardware-verified.
- All lifecycle changes use the existing runtime mutex. Creation and ordinary
  contexts share the same monotonic handle allocator. No new dependencies.

## Verification

CPU tests exercise sharing, lazy creation failure, refcount overflow, per-device
isolation, last release, stale identities, and inactive over-release. Resolver
tests pin version floors and absent legacy/reset/flags APIs. Separate official
CUDA 12.0.107 and CT translation units compare all 29 signatures.

Independent C consumers run as ordinary static imports and LoadLibrary clients
through CT bundles. They check initial state, invalid arguments, TLS independence,
two-thread/shared-memory access, a loaded module across nonfinal release,
last-release invalidation, stale modules/functions, and fresh activation. Existing
CPU, producer, validator, Arc and CUDA consumer lanes remain regression gates.
Raw outputs and binaries stay under ignored local directories.

## Deferred boundaries

P05b reset/reference-generation interaction and P05c nondefault flags/legacy ABI
need separate contracts. Pinned memory, Runtime registration, asynchronous work,
AMD and NVIDIA execution remain unverified. Tombstones intentionally consume
process-lifetime metadata so stale handles cannot silently bind a new context.

## Sources

- [CUDA 12.0.1 primary contexts](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-driver-api/group__CUDA__PRIMARY__CTX.html)
- [CUDA 12.0.1 context management](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-driver-api/group__CUDA__CTX.html)
- Locally pinned CUDA 12.0.107 `cuda.h` and `cudaTypedefs.h`; vendor files are ignored.
