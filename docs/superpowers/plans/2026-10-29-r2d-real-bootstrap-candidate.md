# R2d real CT bootstrap counterfactual plan

> **For agentic workers:** Use superpowers:executing-plans after independent review of this candidate experiment and its execution guards. This is planned work, not a shipping change.

**Goal:** Determine whether the existing real CT initialization/device enumeration works behind the pinned Runtime when only a labelled diagnostic version-response intervention is applied.

**Architecture:** Keep the root production Driver unchanged. Separate an unmodified baseline, a faithful observed baseline and a strictly isolated counterfactual diagnostic child using the exact same CT binary. Preserve actual return values/output writes for forwarded CT initialization and device-count calls; mark the selected version response as an intervention, never nominal compatibility or a supported product version. No full application/kernel workload is permitted in this phase.

**Tech stack:** Existing Windows x64 CT, official Runtime12.9.79, public-header typed diagnostic callbacks, local captures.

**Spec:** `docs/R2C-SYNTHETIC-BOOTSTRAP-RESULTS.md`; the synthetic surface confound requires this separate real-provider experiment before drawing CT conclusions.

## Required design review

- Define the only modified response, fixed sample values and exact labels; distinguish a test intervention from a product version contract. Production cuDriverGetVersion remains801/output0 throughout the experiment.
- Preserve the real provider's lookup surface and both resolver ABIs. Document pointer-wrapping effects and any execution guards as diagnostic differences. Do not silently substitute missing functions or private tables.
- Allow only the Runtime version/device-count prefix. Add correctly typed guards for module/code loading and kernel submission, identical in all observed/control arms; reject any attempted guarded execution before forwarding it. Review device-count/init resource effects and child timeout/cleanup.
- Observe actual cuInit and cuDeviceGetCount calls with official signatures and record their real statuses/output counts. Compare returned Runtime count with direct Driver enumeration in a separate ordinary child. Do not manufacture a device count, NVIDIA name or compute capability.
- If real initialization fails or a new table/API call is needed, preserve it as the next blocker. Opaque lookup alone is not proof of a mandatory dependency and must not prompt fabricated private callbacks.

## Tasks

- [x] Independently review intervention/guard contracts and decide whether the existing observer can be safely extended or needs a separate module. Add failing type/order/identity/guard tests before implementation.
- [x] Capture real baseline and faithful-observer controls, then a fixed-response counterfactual using the same source/provider/SDK identities and process-local loading. Stop before any application launch, unexpected control result or native fault.
- [x] Verify actual init/enumeration behavior, invalid arguments/error propagation and teardown using direct/native controls. Check all root product bytes/HEAD/index remain unchanged.
- [ ] Use that evidence to specify the smallest actual startup bundle and a reviewed compatibility-profile/version meaning. A successful counterfactual prefix alone does not authorize a global CUDA version, full Runtime support or CuPy execution.

## Reviewed implementation contract

An independent read-only design review accepted the bounded experiment with the following gates. Preserve actual CT error ordering: before cuInit, cuDeviceGetCount can return3 before checking a null pointer, while after successful init the same null argument returns1. Never normalize those values.

- Extend the existing Observer only with default faithful hooks and identity-checked binding selection; a separate `real_bootstrap_observer.py` subclass owns intervention, count observation and guards. Both raw GetProcAddress and resolver-returned pointers must match the corresponding CT export before wrapping.
- Always call/log real cuDriverGetVersion first. The separately labelled presentation hook may change801/output0 to0/12000 only for a non-null eligible output. Null/other original results are not eligible; unexpected results latch a callback failure and invalidate the arm.
- Use exact public Win64 signatures for count, module-load and kernel-launch callbacks. No guard dereferences image, function, stream, argument or extra pointers. Module guard clears valid non-null output storage and returns801; launch guard returns801. Any unexpected guard hit stops capture before another arm.
- Catch callback exceptions, record a non-sensitive failure latch and return deterministic failure. Restoration must still run; failures invalidate completion. Native pointer preconditions remain the public ABI's valid-storage requirements.
- IAT restoration does not revoke Runtime-cached function pointers. Keep callback references alive through native DLL teardown. Explicitly unload the owned Runtime DLL after restoring slots while callbacks remain live, then make no further Runtime calls. Record prefix and teardown traces separately and verify module unload. No zero-hidden-leak claim.
- Fixed arms: before nominal, before faithful guarded observation, deliberate guard/ABI contract child, ordinary direct Driver init/count/error/context control, guarded version12000 counterfactual, after faithful and after nominal. Direct guard tests use a separate expected-hit schema; all Runtime arms require zero guard hits/failures.
- A positive counterfactual requires actual successful cuInit, actual successful cuDeviceGetCount, unchanged returned count, agreement with ordinary direct Driver enumeration and passing after-controls. A native fault, guard hit or changed baseline stops execution; a returned Runtime error is preserved as the next unproven dependency, not assigned a guessed cause.
- Check the real source/export lookup inventory for any unguarded module/code-loading or submission route before execution. No CuPy workload or kernel launch is authorized in this phase. Root product code/HEAD/index/protected11 and publication constraints remain unchanged.

Files: `scripts/real_bootstrap_observer.py`, `scripts/real_bootstrap_worker.py`, `scripts/real_bootstrap_check.py`, `scripts/run_real_bootstrap.py`, `tests/test_real_bootstrap.py`, `tests/real_bootstrap_abi.cpp`; default-faithful hook changes in `scripts/cupy_bootstrap_observer.py`. No Cargo/member/product Rust changes.

### Finite sample amendment

Exploration with12000 reached real cuInit success but Runtime36 before an observed count call. Independent design review approved an additional fixed12090 input matching the pinned Runtime's reported version, to test a numeric-threshold explanation. Both samples have separate labels/assertions and identical guarded forwarding; no automatic increase or shipping version claim. Guards now latch within a Runtime call and block subsequent forwarded callbacks; only the explicitly separate guard-contract child allows repeated expected hits.

## Completion boundary

The reviewed negative branch is pinned Runtime36 after real init with no observed count call. Other nonzero statuses, native faults, guard hits or unexpected metadata are preserved privately and stop the runner before its next arm; they cannot be relabelled `diagnostic_pass`.

The result is either a concrete next actual CT bootstrap blocker or independently checked real-provider enumeration under a clearly marked diagnostic intervention. A shipping numeric Driver version remains a separate implementation/policy decision requiring its own contract and evidence. Whole R2/R3, useful application execution and Intel release qualification remain open.

## Recorded outcome

The bounded experiment and independent correction review are complete. Real direct Driver init/count succeeded with one Intel device. Both fixed version-presentation samples reached real init success, then Runtime36 before an observed count call; after-controls matched. See `docs/R2D-REAL-BOOTSTRAP-RESULTS.md`. The final startup-bundle/version-contract task remains open because the next required condition is unresolved.
