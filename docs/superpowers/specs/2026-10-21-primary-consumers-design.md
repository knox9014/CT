# P05c default flags and independent library consumers

Continue approved P05 with explicit default-flags control and independently built
library consumers sharing one CT runtime. Preserve Rust, user files, ignored raw
artifacts and existing process-local CUDA loading.

## Contract

- Add `cuDevicePrimaryCtxSetFlags_v2(device, flags)` (canonical floor11000) and
  `cuCtxGetFlags(unsigned int*)` (floor7000); existing lookup ceiling12000.
  Legacy SetFlags remains absent. GetFlags returns zero for valid current ordinary
  or primary contexts; no current201, stale primary709, null output1. Valid output
  is cleared after initialization before current-context validation.
- SetFlags supports zero before/after activation and while resources exist. It
  neither activates a context nor changes TLS, resources, or reference counts.
  Known flag mask0x1f; scheduling bits0x7 must be0/1/2/4. Unknown bits/combined
  scheduling return1; syntactically valid nonzero flags return801 without effects.
  No legacy active-context708 rule is applied to this v2 API.
- The synchronous Level Zero immediate-list backend blocks inside append calls;
  scheduling cannot be implemented correctly only in cuCtxSynchronize. Nondefault
  scheduling remains deferred. Deprecated MAP_HOST/LMEM bits are also rejected;
  accepting them would not prove CUDA mapped-host/local-memory behavior.
- Two distinct CT-owned library sources are compiled separately. Producer imports
  CUDA statically; consumer loads it dynamically. The unmodified host and both
  DLLs resolve the same application-local nvcuda module. Neither library embeds
  the CT runtime. Explicit library close releases usage; DllMain does no GPU work.
- Producer owns a retain, allocations, module and kernel; consumer owns another
  retain and executes the producer's function/data. After explicit producer close
  and DLL unload, the consumer's retain keeps resources usable. Final consumer
  close invalidates them without changing host TLS. Reloaded producer gets fresh
  resources under existing generation policies.

## Verification and limits

TDD pins flag syntax/support classification and resolver boundaries. Independent
official-header probes cover32 ABI signatures and PFN calls. A native host checks
SetFlags/GetFlags before/after activation/reset, no-op stability, malformed and
unsupported requests, ordinary/stale contexts and output initialization. It then
loads two independent libraries, verifies shared driver identity, executes before/
after producer unload, and exercises fresh activation. Hashes prove unchanged
host/plugin/PTX bytes in test bundles; previous DLL lacks new exports. Each run
changes input and clears output. A separately built negative DLL that skips the
second launch must fail with the execution2 numerical diagnostic.

The test harness copies explicitly named libraries into ignored local bundles;
the public loader does not acquire automatic dependency discovery or library
packaging. This proves CT-owned multi-library consumers, not third-party library,
Runtime, framework, scheduling, AMD/NVIDIA or full P05 compatibility. P05b's
fresh-handle-after-reset and native raw-address reuse limits remain unchanged.

Sources: pinned CUDA12.0.107 headers and
[primary contexts](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-driver-api/group__CUDA__PRIMARY__CTX.html),
[context queries](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-driver-api/group__CUDA__CTX.html).
