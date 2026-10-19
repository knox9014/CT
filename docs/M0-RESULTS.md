# M0: Arc B390 native execution evidence

Date: 2026-10-19. Result: **M0 native execution passed on the recorded environment. CUDA compatibility is not implemented.**

## What ran

The Rust executable loaded the installed System32 Level Zero loader, selected Intel vendor 0x8086 / device 0xb080, created a context and compute queue, compiled the synthetic SPIR-V fixture, allocated distinct host/device memory, copied inputs, dispatched vector addition, synchronized, copied output back and validated it. Successful cleanup API results are required before a pass report is emitted.

| Input lengths | Group sizes | Cases | Checked results | Guard values | Max absolute error |
| --- | --- | --- | --- | --- | --- |
| 1, 63, 64, 65, 255, 256, 257, 100003 | 64, 128 | 16 | 201928 | 1536 | 0 |

Output starts as NaN. A one-group guard region follows logical output and must retain its sentinel values. A controlled fixture with the output store removed failed with `nonfinite value at index 0` and exit code 1. This demonstrates that a no-op dispatch is not accepted as successful computation.

The GPU test was first run against an unimplemented stub and failed, then passed after native execution was implemented. Three host-side validation tests cover incorrect/no-op outputs, nonfinite values/length mismatches, and dispatch rounding/overflow.

## Reproduce

Requires Windows x64, Rust/MSVC, an installed Intel Level Zero driver, and a matching GPU. Running requires no downloaded SDK or Rust package dependencies. Default GPU filter is B390; an explicit alternate filter is only an experiment, not a claim of device support.

```powershell
$env:CARGO_INCREMENTAL = '0'
python scripts/generate_smoke_spirv.py
cargo test --workspace
cargo test --workspace --test gpu -- --ignored --nocapture
cargo run --quiet --bin ct-intel-smoke -- tests/fixtures/vector_add.spv B390
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
```

Default cargo test leaves the GPU test ignored; the explicit second test command is needed for hardware verification. CARGO_INCREMENTAL=0 avoids a hard-link warning seen under this sandbox; it does not change GPU execution.

CLI stdout is one JSON report; progress and errors go to stderr. Failure exits nonzero. Locally saved reports/logs are ignored under `results/local/`; they are not needed for the public summary.

### FFI ABI comparison

Download the official reference header, then compile the C oracle and compare all 12 C/Rust layouts. This is a developer check, not required for each smoke execution. Requires PowerShell 7 and MSVC C++ tools; the script verifies the header hash before use.

```powershell
New-Item -ItemType Directory -Force .cache/reference | Out-Null
Invoke-WebRequest https://raw.githubusercontent.com/oneapi-src/level-zero/v1.27.0/include/ze_api.h -OutFile .cache/reference/ze_api.h
pwsh -NoProfile -File scripts/check_level_zero_abi.ps1
```

Observed: `ABI match: 12 structures, every field offset, size and alignment.`

### Fixture provenance

- Readable source: `tests/fixtures/vector_add.spvasm`.
- Encoder: `scripts/generate_smoke_spirv.py`; fixed subset, not a production compiler.
- Binary: 584 bytes, SHA-256 `78c122989c637046319c5661a18aa0f2b9206407c63ea28ac261d1b6f6e64ca4`.
- Reference header SHA-256: `3e7967d37ce79a472205c9cc230da837173ba390686bc4017e980e1290e40feb`.
- Khronos reference: https://github.com/KhronosGroup/SPIRV-Headers/tree/vulkan-sdk-1.4.328.1/include/spirv/unified1
- Level Zero reference: https://github.com/oneapi-src/level-zero/blob/v1.27.0/include/ze_api.h

## Limits

Official spirv-val was not available and was not run. Driver module compilation and actual numerical execution passed; this is not a substitute claim of full SPIR-V specification validation. Device loss, timeout, allocation failure, missing driver and every partial-cleanup failure have not been fault-injected. The fixture exercises only bounded FP32 addition with exact binary-fraction inputs, not general floating-point conformance or CUDA execution. No performance benchmark was performed.

Next scope: design and implement M1's narrow CUDA API/ABI and resource contract on this verified native foundation. M0 code is experimental test infrastructure; it is not a production CUDA driver.
