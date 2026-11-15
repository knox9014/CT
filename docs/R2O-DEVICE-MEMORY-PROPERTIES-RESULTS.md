# R2o: device-reported memory total foundation

The optional Intel backend total_memory query now returns the nonzero total_size of a single Level Zero memory property when its initial count, fill count and final count observations are all1. Multiple properties, zero totals and inconsistent counts return unsupported. It never guesses a RAM fraction, sums unverified domains, queries free memory or allocates GPU-wide memory. Backend::open has no new memory-query dependency.

On the selected Intel(R) Arc(TM) B390 GPU, one explicit ignored native testcase passed. Two complete queries each returned17578409984 bytes. This is a UMD-advertised total with matching observed counts, not fixed physical VRAM, current free/budgeted memory, guaranteed allocatable capacity or an atomic property snapshot. The [Level Zero API](https://oneapi-src.github.io/level-zero-spec/level-zero/1.18.31/core/api/apis/device.html#zedevicegetmemoryproperties) defines the property query; [Intel's accounting guide](https://github.com/intel/compute-runtime/blob/master/programmers-guide/DEVICE_MEMORY_ACCOUNTING.md) distinguishes these accounting layers.

The minimal DeviceMemoryProperties C layout is checked against the pinned official Level Zero v1.27.0 header. Actual C/Rust outputs matched all13 structures and field offsets. The memory type has size296, alignment8, total_size offset32 and name offset40. A separate official-header-only compile proof verifies stype7 and the ZE_APICALL function-pointer signature. The Rust query uses extern C and initializes stype7/nextnull/capacity1 before fill.

Missing optional symbol returns unsupported before any native call. Invalid index is rejected first. Errors at any of the three native query stages retain their codes; device-lost/reset sets loader keep_loaded without inventing a Context poison target or automatically retrying. Four fake-FFI tests cover64-bit1<<40 data, exact capacity/nullness/stype/next/device arguments, missing API, zero/multiple/drifting counts, zero total and all error stages. One Rust ABI test checks the expected x64 layout. Tests were written first and failed on missing method/type before implementation. Independent review repeated all5 focused tests before native execution.

The clean private checkpoint passed CPU11/11: Python334, Rust220 with7 ignored tests, Runtime129, formatting, Clippy and registry/profile/publication checks. The new native metadata test passed separately; CPU did not implicitly execute it or the other6 ignored cases. Final privacy/source checks are recorded in the ignored local final-verification record. No CUDA export, header, resolver, version or profile is added in this stage; the following public wrapper still needs its exact size_t ABI and legacy-version refusal.

Source fingerprint: `94782f34d0a95a64b2e05fc4d49f76452ef26eb4f8293f9d23a10d64d6a54e7f`. Private checkpoint commit: `e00f9bb586feb0a096a423f6d49d68a467fef585`; tree: `a64f233bcae3c424fb345965701c6570b6233d73`. The pinned header SHA256 is `3e7967d37ce79a472205c9cc230da837173ba390686bc4017e980e1290e40feb`. Ignored local capture binds source/checkpoint, commands, compiler/header, C/Rust layout outputs, signature object and native log.

Reproduce focused checks with `cargo test -p ct-backend-intel --lib memory_total` and `cargo test -p ct-level-zero --lib device_memory`. Explicit hardware check:

```text
cargo test --locked -p ct-backend-intel --test memory_totals native_device_total_reports_single_driver_memory_property -- --ignored --exact --nocapture --test-threads=1
```

Run the layout oracle with scripts/check_level_zero_abi.ps1 using the pinned local header and compile tests/device_memory_reference_abi.cpp against that header. Raw reference headers, binaries, commands with absolute paths and logs remain ignored. No root staging/commit, upload, installation or managed-worktree edits were performed.

Next expose the bounded total through cuDeviceTotalMem_v2 with the v3020 size_t pointer ABI, reject legacyv2000 lookup, preserve thread context and update current-source ABI/export validators and negative-control forwarders. Historical captures/reports retain their original export scopes. No CUDA application support is claimed here.
