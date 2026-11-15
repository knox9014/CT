# Genuine nvcc relaxed global operands: Arc diagnostic result

Verified 2026-10-26. This extends the [synthetic relaxed-memory checks](RELAXED-MEMORY-RESULTS.md)
with a genuine compiler-generated CUDA consumer. It is working-checkout diagnostic
evidence over `219e6e5`, including the uncommitted relaxed-memory implementation;
not a clean immutable acceptance, release or upstream application claim.

## What was actually connected

The CT-owned [CUDA C++ source](../tests/fixtures/relaxed_nvcc_runtime.cu) was compiled
with authenticated local CUDA 12.0.76 tools, shared cudart, default device-runtime
registration and the existing diagnostic MSVC override. No inline assembly,
post-compilation PTX editing or executable patching was used. The unchanged EXE
ran with app-local CT Runtime and Driver DLLs through Level Zero on
**Intel(R) Arc(TM) B390 GPU**, identified by the consumer through cuDeviceGetName.

The compiler naturally generated both operations with a declared b64 register:

```ptx
ld.volatile.global.u32 %rd1, [ct_narrow];
st.volatile.global.u32 [ct_narrow], %rd1;
```

The diagnostic checks each instruction in its own producer entry. Kept PTX and
the decoded fatbin have identical token streams after ignoring compiler-removed
comments/formatting. Both original kept fatbin byte sequences were also located
inside the final EXE during verification. No substitute kernels were used.

Named scalar globals deliberately isolate this feature from the separately
documented general-pointer alignment gap. This is not evidence that unannotated
pointer parameters now support arbitrary mixed-width memory accesses.

## Execution and controls

- Initial capture: **2 positive processes + 1 forwarding launch-noop process**.
- Independent replay: same saved EXE/DLLs, **2 more positive processes + 1 noop**,
  with three new random seeds distinct from all initial seeds.
- Each process performs 8 cases, each with two kernel launches and 10 observed
  host readback words: 32 positive cases and 16 control cases across 6 processes.
- The Python oracle independently calculates zero extension, low-32-bit
  truncation, high-bit/all-one cases, seeded values and every host guard word.
- Noop preserves the real module/symbol/copy path while suppressing launches.
  Its full observations match the separate noop oracle and fail the positive
  oracle. Successful exit status alone cannot pass the test.
- Original artifacts and bundle EXE/DLL bytes were hashed before and after
  execution. Replay checks the original manifest/source identity and saves its
  new observations bound to the original manifest hash.

The guards here surround **host copy destinations**. They do not independently
prove adjacent device-global bytes are preserved. The prior synthetic pointer
regression checks device neighboring words, while typed lowering tests and the
validator check the four-byte access representation. These are separate evidence
scopes and must not be conflated.

`--audit` verifies saved bytes/schema/oracles without executing GPU work and
reports `execution_performed:false`. `--replay` performs fresh native execution.

## Verification and identities

- Rust workspace: **141 passed, 0 failed, 3 ignored**; ignored tests not enabled.
- Standalone Runtime: **77 passed**. Python discovery: **161 passed**, including
  9 new tests for numerical/schema mutations, noop detection, actual register
  shapes, changed/escaped files, wrong DLL roles and saved-run corruption.
- Workspace fmt/clippy passed. Pinned spirv-val accepted SPIR-V translated from
  the genuine producer's two-entry PTX with `opencl1.2`.
- Independent source review's replay/device-identity gaps were fixed and
  re-reviewed without new actionable findings. Reviewer did not execute tests.
- User-owned 11-file preservation and publication-pattern checks are recorded
  separately from functional/security guarantees. This is not a full security audit.

| Identity | SHA256 |
| --- | --- |
| Source fingerprint | `7dbd703e742d20dd303f0ecd5120977856f68c4b12f6e1facecc4950f5288596` |
| Original EXE | `42c01fbd0aa2a005df492eb659b418629353332fb1ca2ec47ed935c7832f9070` |
| Driver DLL | `92babad4ba894e9ea5628e27f3d1d27503a23af04320770ddc7f8c8be4f52b53` |
| Runtime DLL | `525891a518080f6f88556aa0df6d4144fb53f3847c69202ad50a9dc15d411ed5` |
| Kept producer PTX | `93e406e37a611d905ffd6955556c0a72a2748ae9803cf438d4fe8871a4550057` |
| Generated SPIR-V | `5eb64e36cc07034ed6027ee3950bfb7e53a134835fc448c7f814c83d897bc996` |
| Capture manifest | `16514eb0d1f41bee0734a4f8990e1b0fa2b47ef5017aac2e75ffc9b6c65a37d2` |

Manifests, compiler/tool paths, raw observations and binaries remain ignored under
`.cache/relaxed-nvcc-runs/`. `.cache/relaxed-nvcc-latest.json` points to the verified
capture. Earlier exploratory captures remain local and are not current evidence.

## Reproduction

```powershell
python scripts/run_relaxed_nvcc.py
# Use the manifest path from the local latest pointer for the saved capture:
$taskCapture = (Get-Content -Raw .cache/relaxed-nvcc-latest.json | ConvertFrom-Json).manifest
python scripts/run_relaxed_nvcc.py --audit $taskCapture
python scripts/run_relaxed_nvcc.py --replay $taskCapture
python -m unittest discover -s tests -p test_relaxed_nvcc.py
```

The build command itself does not update the latest pointer; it creates a unique
capture directory. The recorded latest pointer above was written after the
successful independent replay in this verification session. A new capture can
be selected from its local `manifest.json` after checking the reported EXE hash.

## Remaining boundaries

No static cudart, general device-runtime function/device linking, signed widened
memory operations, arbitrary CUDA apps, supported-host qualification, AMD or
NVIDIA numerical parity, performance or universal-completion claim is added.
The historical 52-case clean lane has not been extended or rerun here.

Next, use real application first failures to select signed widening versus
access-specific pointer alignment work, while retaining shared memory/barrier
and asynchronous lifetime work on the broader roadmap.
