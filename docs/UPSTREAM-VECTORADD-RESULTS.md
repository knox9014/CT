# Original NVIDIA Runtime vectorAdd: external diagnostic result

Verified 2026-10-26. This is an **upstream_adjusted_build** diagnostic on the
working checkout, not original build-recipe/distributed-binary compatibility,
clean acceptance, release or general CUDA support. No new nominal CUDA exports
or product behavior were added in this step.

## Original source, explicit build changes

[NVIDIA CUDA Samples vectorAdd](https://github.com/NVIDIA/cuda-samples/blob/2b689228b746248b7bb7d2778d5ea0701669f7d3/Samples/0_Introduction/vectorAdd/vectorAdd.cu)
was fixed at commit `2b689228b746248b7bb7d2778d5ea0701669f7d3`.
Its Git blob is `284b0f0e332f022ed6789456182238fc2fc6af54`; source SHA256 is
`9a156c7c4f1ab0759d859af95c8dab55f2280d867edca7daee4546d63effb583`.
Both Common helper headers were copied from the same pinned Git objects and
individually hashed. Original copyright/license notices remain intact locally.
No vendor source is committed or publicly bundled by this change.

Host and kernel source bytes are unchanged. The custom nvcc12.0.76 recipe uses
shared cudart, PTX8/sm52, default device-runtime registration and the existing
diagnostic MSVC override. Changing from a normal/default build to this recipe is
why this is not the original upstream build. No EXE/PTX patching or substitute
kernel is used. Kept PTX matches the fatbin token stream and both kept fatbin
byte sequences are present inside the original generated EXE.

## What actually ran

| Mode | Application and provider | Result |
| --- | --- | --- |
| Nominal | Unchanged EXE + actual CT Runtime/Driver DLLs | Original50000-element test completed |
| Observed | Same EXE/Runtime; observational Driver forwards to the same CT Driver | All50000 actual output words match independent exact float32 sums |
| Launch-noop control | Same EXE/Runtime; observer captures inputs but skips launch | Sample still prints PASS with NaN output; CT's independent oracle rejects it |

All three modes ran once at capture and again from the same saved bytes in fresh
processes: **6 external processes total**, including2 nominal,2 observed and2
intentional negative controls. The observed underlying device is
**Intel(R) Arc(TM) B390 GPU**, through Level Zero. Source and byte identities are
shared between modes; the observational provider is explicitly distinct from the
nominal product DLL.

The sample calls rand without seeding it. These are deterministic fresh-process
replays, not new-seed/new-data claims. Trace and control input hashes match, and
replay inputs must match the original trace. Original and bundle EXE/DLL hashes
are checked before/after execution.

## Why the sample's PASS message is insufficient

This pinned source checks `fabs(expected - actual) > tolerance`. In the deliberate
noop mode the observer poisons unspecified allocation contents with quiet NaN;
no kernel runs, but comparisons with NaN do not trigger this host failure test.
The sample therefore returns0 and prints its success text in that control.

CT does **not** count that as a successful computation. The independent oracle
requires correctly sized finite-domain input captures, finite output, and every
float32 sum bit. It rejects the exact50000-word NaN poison. The observer records
actual HtoD/DtoH bytes and checks allocation roles, launch arguments/dimensions,
forwarded-versus-skipped launch counts and frees; it never computes output sums.
Positive observed allocations are also poisoned, so missing writes cannot be
silently accepted. The unmodified nominal product run does not use this poisoning.

Independent data checks cover **100000 positive output elements** over the two
observed processes. This specific Runtime app allocates exactly its requested
buffers; no claim of device-neighbor guards is made for its raw captures.

## Independent actual-kernel checks

The real compiled producer PTX was also executed directly through the nominal
CT Driver using separate finite input vectors, poisoned outputs and64 trailing
guards. Sizes1/63/64/65/257/50000 each passed at capture and replay:
**12 cases /100900 numerical results /768 guards** in total. These are independent
Driver tests of the same compiled kernel, not additional upstream applications
or original Runtime inputs. Their entry is `_Z9vectorAddPKfS0_Pfi`.

## Verification and review

- Rust workspace: **151 passed, 0 failed, 3 ignored**. Runtime: **77 passed**.
- Python discovery: **172 passed**, including7 new observer/oracle regressions.
- Workspace fmt/clippy passed. Pinned spirv-val accepted the real producer module
  with `opencl1.2`. Compatibility/Runtime/coverage static checks passed; static
  validity is not execution evidence for every registry case.
- Independent review found two verification gaps: noop input validity and Python
  optimization disabling the legacy Driver helper's assertions. Regression tests
  reproduced both; input checks/hash coupling and explicit optimized-execution
  rejection fixed them before final capture. Re-review found no further actionable
  issue. Reviewer did not build or execute GPU work.
- Saved-only `--audit` reports execution_performed:false. Build/replay require
  unoptimized Python because the reused guarded Driver helper uses assertions.

## Identities

| Item | SHA256 |
| --- | --- |
| Source fingerprint | `cbdb1a83ca4cb1aef29036b9fbf167e9a7bc9932340d5f120559d6891456eb3b` |
| Capture manifest | `7878ca86a2099fe967c9ddbae17901ce8c5fb0561e044f3b9cbf7be8f7dd1ce4` |
| Original generated EXE | `daec8c7b21c9294de04ef4924d844458c0e43e07fb867ddc415394d912e0fc79` |
| Nominal underlying Driver | `d36e9bb0dcc9bd8c7fa709a2c6ce43c19767585be9572424cfbd72efac495f4f` |
| Runtime | `1e43fbae21dbc1e7072abdfedf65b89eaa37e5792e0802867a70b0d175a22107` |
| Producer PTX | `d0140bcb3706c939ac72b2b5239c1068cecbebc4b180b95f78c6378c51f9f0d1` |
| Validated SPIR-V | `13c0c3b5ef9228ddd7db9cce512050c28092537f712f9155686c574770b782b5` |
| Observed output, both runs | `e5d786bcfe8dc846c8f2ad5e380e27a368682a62a03ea189955bb1661c38ddd4` |

## Reproduction and remaining work

```powershell
python scripts/run_upstream_vectoradd.py
# Build prints its manifest. For this session's independently replayed capture:
$taskCapture = (Get-Content -Raw .cache/upstream-vectoradd-latest.json | ConvertFrom-Json).manifest
python scripts/run_upstream_vectoradd.py --audit $taskCapture
python scripts/run_upstream_vectoradd.py --replay $taskCapture
python -m unittest discover -s tests -p test_upstream_vectoradd.py
```

The source cache must contain the exact pinned files; the runner checks hashes
and does not fetch an arbitrary latest source. This session used the GitHub
connector to retrieve the missing source and verified its bytes against the
pinned Git blob. The latest pointer was written after successful replay; new
builds print unique capture paths. Raw sources, buffers, paths, binaries and
manifests remain ignored. Existing user-owned files remain preserved.

This result extends the prior CT-owned fixtures to one original external Runtime
sample. The historical application registry and52-case clean lane are not silently
promoted or requalified by this diagnostic. No static cudart, supported-host,
AMD/NVIDIA parity, performance, framework or universal-completion claim follows.
Next, pin a more demanding external sample and record its first real API/PTX
blocker before selecting another feature expansion.
