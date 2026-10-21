# P05b primary reset design

## Intent and scope

Extend the approved P05 work so CUDA Driver consumers can explicitly reset a
primary context without losing retained usage. Preserve Rust, local bundles,
user files and publication privacy. This is the default-flags v2 reset slice;
it does not establish complete CUDA or NVIDIA behavior parity.

## Contract and decisions

- Add `cuDevicePrimaryCtxReset_v2(CUdevice)`; canonical resolver name
  `cuDevicePrimaryCtxReset`, floor11000, ceiling12000. Legacy Reset remains
  unavailable, rather than treating equal signatures as equal semantics.
- Track retained usage separately from the optional active context generation.
  Reset takes the active context, tombstones its handle, clears public resource
  ownership and performs existing cleanup. It does not decrement references.
  GetState reports inactive after reset even while references remain.
- Reset on an unused or already inactive valid device succeeds without creating
  native resources, changing TLS, or discarding references. Invalid device and
  uninitialized calls retain existing error categories101 and3.
- Releases after reset safely consume retained usage. Over-release returns201.
  Retain after reset lazily creates a fresh generation and increments the existing
  count only after successful creation. Old references still count toward the
  new active generation's final release. Failed creation/overflow preserve state.
- Reset never edits any thread's TLS. Old context handles remain stale709 under
  the P05a policy. Explicit pop-by-SetCurrent(NULL) recovers the previous stack;
  old handles are not silently rebound to new native resources. Module/function
  handles are monotonic and remain invalid across reactivation.
- Cleanup failure returns the original error, leaves inactive ownership and
  preserved references, quarantines uncertain resources, and does not retry them
  on repeated reset or later release. Fresh retain is an explicit user action.
- The existing runtime mutex serializes API calls. Callers must coordinate reset
  with other consumers; no asynchronous/in-flight support is added.

## Evidence boundaries and alternatives

Release-on-reset would lose required retained usage, so it is rejected. Retaining
a native context shell after cleanup would require backend reset and lazy native
reactivation semantics not yet specified. This bounded implementation uses fresh
monotonic generations, consistent with P05a stale-handle policy. CUDA12.0 docs
do not fix post-reset handle identity or exact GetCurrent behavior; this CT policy
is explicitly NVIDIA-unverified and may constrain external consumers that reuse
old CUcontext values. Device-pointer values are native addresses and may be
reused after deallocation; no generation safety is claimed for stale raw pointers.

## Verification

Pure-state tests cover retained inactive state, repeated/no-op reset, releases
after reset, fresh retain with outstanding usage, failed reactivation, overflow,
and per-device isolation. Integrated helpers inject cleanup failure and verify
no retry through reset/release/reactivation. Resolver tests and independent
official-header ABI probes pin the new signature and version boundaries.

Ordinary static/dynamic C consumers use two threads and coordinated reset,
with memory, modules and kernels before/after reset. They verify stale TLS,
stale resource handles, ordinary-context isolation and remaining release counts.
Existing P05a and all CPU/compiler/validator/Arc lanes remain required. Real
hardware faults, AMD/NVIDIA and framework/runtime support remain unverified.

## Sources

[CUDA12.0.1 primary contexts](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-driver-api/group__CUDA__PRIMARY__CTX.html)
and ignored, pinned CUDA12.0.107 `cuda.h` / `cudaTypedefs.h`.
