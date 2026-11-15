# Public total memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose the qualified driver-advertised total through CUDA's exact v3020 size_t-pointer interface.

**Architecture:** New cuDeviceTotalMem_v2 wrapper clears output before invoke, requires initialized/valid device and converts the R2o u64 total to size_t without truncation. Canonical resolver name cuDeviceTotalMem begins3020, maximum12000, no legacyv2000 or suffix alias. Add47th current Driver export plus bounded registry declarations and official-header native consumer. Existing negative-control forwarders/count validators must grow with the current header; historical reports/captures and unrelated Runtime counts stay unchanged.

**Tech Stack:** Rust Driver/backend, official CUDA header ABI comparison/native PFN consumer, C forwarding provider, Python/registry tests, private clean CPU checkpoint.

**Spec:** R2O-DEVICE-MEMORY-PROPERTIES-RESULTS.md, pinned cudaTypedefs.h PFN_cuDeviceTotalMem_v3020 and this design.

## Constraints and review focus

- Legacy2000 uses a4-byte output and must never be bound to this8-byte implementation. Test2000/3019refusal,3020success, suffix missing and output canaries.
- Valid output is cleared on all failures including lock failure; null returns1. Invalid ordinal returns101 after init. No context required or TLS changes; no activation of a primary context.
- Return only R2o single-property driver-advertised total. No physical/free/budget or broad version conformance claims.
- Keep production version801/output0;47exports reflects current-source surface, not measured app support.
- Preserve protected11/HEAD/index/previous work; no root staging/commit/upload/install or managed-worktree edits.
- Mechanical changes assigned to agent: proxyforwarder,2nativeexportcounts,2ABIvalidators,2Pythoncountfixtures and PowerShellcountoutput only. Parent owns wrapper/header/resolver/profiles/docs/newconsumer.

Review ruling: native consumer counts are fixed39nominal/42forwarded; enforce them rather than a broad interval. The forwarded unload result means only the selected proxy DLL is unloaded; its original forwarding implementation retains the underlying provider until process exit. Do not claim complete provider unload in that arm.

Build ruling: first native producer121dee33f19a4dbaa6c312ecb1240ee2 failed linking before any native child. The base p09a_noop_driver.c intentionally lacks8 later host/event/global exports. Compile the existing full host_memory_driver_proxy.c include chain (which includes that base and its new memory forwarder) for the47-export smoke. Preserve the failed build; no production/API change or passing-gate change is needed.

## Tasks

- [x] Add failing typed-null/uninitialized unit and resolverboundary tests before implementing wrapper.
- [x] Implement Rust/header/resolver and bounded registry declarations. Update official reference probe and current-source forwarding/count dependencies. Run focused tests and independent review.
- [x] Freeze source; full required CPU plus original-header declared/reference ABI comparison, actual47exports, official-PFN native consumer and shared forwarding-provider smoke. Inspect samedevice/bytes/TLS/preconditions/legacyrefusal.
- [x] Verify privacy/protected11/HEAD/index and source/artifacts; record results and continue guarded Runtime prefix beyond name/memory queries.
