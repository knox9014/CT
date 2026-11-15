# Virtual topology count implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline; use a fresh independent final review.

**Goal:** Implement attribute16 through CT Driver/Runtime in the explicit software target, with separately measured Intel topology provenance.

**Architecture:** Retain raw Level Zero maximum slice/subslice dimensions in Backend Device, without validation that could reject device enumeration. In Driver policy code, strict16 remains801; ct-sm52-subset-v1 reports checked positive max_slices*max_subslices_per_slice fittingi32. This is a CT software-target topology count derived from maximum native dimensions, not active NVIDIA SMs, Intel EUs, occupancy or performance ranking. Runtime forwards16 through its owned Driver binding without reading configuration or acquiring a context. No guessed1, clamp, fallback or physical SM claim.

**Sources:** Intel Xe architecture guide (2025-2) demonstrates slice*subslice topology; Level Zero ze_device_properties_t defines these as maximum dimensions. Independent design review requires retaining raw fields and bounding claims accordingly.

**Scope:** Product metadata + actual CT Runtime/Driver ABI qualification. A new official NVIDIA Runtime prefix beyond16 follows separately; historical R2t capture must fail fast on incompatible source while immutable replay remains available.

## Global constraints / review focus

Preserve rootHEAD/index/protected11, all unrelated work and managed worktrees; no root staging/commit/push. Use private source candidates and ignored ledger; user delegated routine design choices. Strict policy/75/76/version behavior stays unchanged. Driver errors zero a valid output after initialization; Runtime preserves output on all errors and preserves prior TLS error on success. Do not treat zero/overflow topology as device failure. Raw dimensions are maximum topology, never EU/active-SM counts. Independent native control must uniquely identify the sole Intel GPU, match name/count and verify stable physical properties without publishing deviceUUIDs. Keep keys notebook-only and Drive units encrypted; bound native/CPU output and reclaim only verified reproducible temporaries.

### Task1: Raw topology and policy conversion

- [x] RED: zero dimensions, normal product, exacti32 maximum, i32/u32 overflow, strict valid/invalid metadata rejection; Runtime16 actualdevicehandle forwarding.
- [x] GREEN: raw topology dimensions in backend; checked conversion only in Driver virtual policy; Runtime whitelist16 and updated contract/profile metadata. Update existing fakeDevice construction and native virtual-target16 assertions.
- [x] Retire R2t fresh capture before budget/native work, with regression; preserve frozen historical checkers and saved audits.

### Task2: Independent native ABI and clean qualification

- [x] RED/GREEN independent Python topology oracle and guard/source/file identity tests.
- [x] Add guarded topology runner reusing the five existing attribute-loader controls and one shared parent Cargo target. Compile official CUDA/LevelZero-header topology consumer and existing virtual-policy consumer; run strict/virtual initialization orders, minimal owned binding, loader negatives and existing policy ABI modes including late unsupported-code refusal.
- [x] Independently query the sole Intel GPU through system LevelZero loader. Check native dimensions/identity before+after and compare checked maximum topology product to both CT APIs; retain canaries/TLS/context/immutability/invalid-ordinal assertions.
- [x] Independent pre-native review, final source freeze, cleanCPU11 lanes and actual native captures, then saved evidence consistency audit. Remove only dedicated CPUtarget after clean report verification before native builds if necessary for headroom.

### Task3: Review, recovery and retention

- [x] Fresh independent bounded final review; record exact qualification and remaining official Runtime/application limits; publication/index/protected verification.
- [x] Encrypt final source/report/native ABI closure, upload to private Drive, verify readback and full restore before cleanup.
- [x] Retain latest binaries/observations and the warm R2t Runtime closure; reclaim new ABI Cargo target and transfer/restore duplicates after recovery proof. Update recovery catalog and cache delta.
