# Access-specific pointer alignment: genuine nvcc Arc diagnostic

Verified 2026-10-26. Working-checkout evidence over `219e6e5` plus the uncommitted
relaxed-memory and alignment changes; not a clean acceptance or release.
Historical [P04c](P04c-RESULTS.md) and [relaxed nvcc](RELAXED-NVCC-RESULTS.md)
captures remain preserved as dated evidence, not current source-tree passes.

## Problem and resulting behavior

The old parser rejected an entire kernel containing any register-address U64
memory access if even one unrelated pointer had less than8-byte alignment. It
also left genuine nvcc's unannotated pointers at4, blocking natural mixed-width
programs. Removing that gate alone would not justify emitting aligned U64 accesses.

CT now runs a bounded CFG analysis that tracks unique pointer origins and possible
low3-bit values. It validates wide access addresses after reaching a fixed point,
including branch joins and loop iterations. Unsupported/unknown origins, forged
scalar addresses and uncertain alignment are rejected. A4096 block-visit budget
fails closed rather than accepting incomplete analysis.

Only inferred pointer parameters actually used as roots of U64 accesses gain an
8-byte launch contract. Explicit align4 roots stay ineligible. Narrow-only and
unrelated parameters keep4-byte contracts. Named scalar globals retain their
separate typed-storage path. Existing runtime base-alignment/minimum-extent
checks and native signature generation consume the resulting parameter metadata.

The abstract analysis covers mov/cvta, integer U64-to-U64 conversion, pointer plus
scalar or minus scalar, scalar modular arithmetic/bit operations and literal left
shifts. Mixed-origin joins and unsupported pointer transformations may conservatively
reject valid programs. This is not a proof of derived-address bounds or ownership.
The legacy32-bit-address path is not expanded by this work.

## Actual compiler/application connection

The [CT-owned CUDA source](../tests/fixtures/alignment_nvcc_runtime.cu) was compiled
by authenticated local nvcc12.0.76 with shared cudart, default device-runtime
registration and the existing diagnostic host override. The generated PTX and
EXE were not patched. Kept PTX matches the fatbin's token stream, and both kept
fatbin byte sequences were found inside the EXE.

Both real producer entries have two unannotated `.param.u64` arguments:

| Entry | Resulting pointer contracts | Observed behavior |
| --- | --- | --- |
| `widen_array` | output8 / input4 | U32 input widened into U64 output |
| `copy_narrow` | output4 / input4 | Narrow-only contract remains usable |

The input and narrow output are allocation base +260 bytes, hence4mod8 under
the backend's64-byte allocation-alignment request. The wide output is base +512.
The genuine SPIR-V signatures were independently inspected: `[16,8,3]` for widen
and `[8,8,3]` for copy, matching the emitter's wide-pointer/narrow-pointer/U32 types.

Before valid launches the consumer passes a wide-output base +4. The positive
provider returns CT error1 and a full readback confirms no output change. This
is CT's preflight policy, not a measured NVIDIA error-precedence parity claim.

## Executed checks and controls

- **4 positive processes**, two captured and two replayed with new seeds: each
  widens17 elements, copies17 narrow elements, and checks rejection of the
  misaligned wide argument.
- **2 forwarding launch-noop processes**, capture plus replay. Suppressed launches
  leave original data intact; the separate control oracle expects status0 for
  the skipped invalid launch and is explicitly rejected by the positive oracle.
- All4 device buffers are read back in full:147 words each, including input,
  narrow output, wide output, and wide output immediately after the invalid call.
  Guards here are actual device-buffer neighbors, unlike the previous named-global
  consumer's host-only copy guards.
- Original and bundled EXE/DLL hashes remain unchanged. Replay excludes every
  original seed and binds new observations to the original manifest hash.
- The identical EXE with the previous pinned Driver DLL
  `92babad4ba894e9ea5628e27f3d1d27503a23af04320770ddc7f8c8be4f52b53`
  did not complete (consumer exit42, original bytes preserved). This is a
  previous-CT control, not an NVIDIA run; raw failure output stays local.
- Consumer-reported device: **Intel(R) Arc(TM) B390 GPU**, through Level Zero.

## CPU, validator and review evidence

- Rust workspace **151 passed, 0 failed, 3 ignored**. Runtime **77 passed**.
- Python **165 passed**. Workspace fmt/clippy with warnings denied passed.
- Pinned spirv-val accepted the real producer's translated two-entry module under
  `opencl1.2`. Compatibility/Runtime/coverage registries passed static checks;
  these do not imply execution of every registered case.
- New tests cover unrelated align4 pointers, selective inferred promotion,
  forged/scalar addresses, same/different-root joins, loop step8 versus4,
  in-place changes, load clobbering its own address register, conversion widths,
  literal shift counts, explicit align4 rejection and budget exhaustion.
- Before implementation the first6 alignment regressions failed on the old
  global gate or its acceptance of unproved addresses. One old signed-literal
  test used a computed scalar as an address; it now stores the same literal to a
  declared global, retaining literal coverage under the new proof requirement.
- Independent design and source review found no blocking issue. Reviews were
  read-only and did not execute tests/GPU work.

## Identities

| Item | SHA256 |
| --- | --- |
| Source fingerprint | `52d426705233f4e352d31a1e0dd31734c25247fd27deff3cb467c8cf04bc42a4` |
| Manifest | `ee5630d623eea9587049a121c272d5ad7bab4fc92d3013acbd856828d26a3842` |
| Original EXE | `a30145c4d7103870a04b267f58314debd20666f222143b26e8b24f0f94656790` |
| Driver | `56bd8077f4af0353ef4909d6f8aa7da4b72ae9a43f62072c50e6755791cb44c7` |
| Runtime | `9dd4f435f34f83c0a48dda0edbe61d7b6bc256e9e4ec82ed9c48e84174b0e7c1` |
| Producer PTX | `75b906d21992f4290cf0ae43544e19ff1903b01cc404c9c4ba75f8522cda7efe` |
| Validated SPIR-V | `7a9bce27c18a8090168e4ec0ccd63280a859df2dfc2ebacbc04229400329b56d` |

## Local reproduction and limits

```powershell
python scripts/run_alignment_nvcc.py
# Build prints its relative manifest path; the recorded verification pointer is:
$taskCapture = (Get-Content -Raw .cache/alignment-nvcc-latest.json | ConvertFrom-Json).manifest
python scripts/run_alignment_nvcc.py --audit $taskCapture
python scripts/run_alignment_nvcc.py --replay $taskCapture
cargo test -p ct-ptx --test alignment --target-dir .cache/pointer-alignment-target
python -m unittest discover -s tests -p test_alignment_nvcc.py
```

The pointer was written after this session's verified replay; a new build prints
its own manifest rather than changing the pointer automatically. `--audit`
checks saved evidence only and reports execution_performed:false. Raw compiler
paths, logs, manifests and binaries stay ignored under `.cache`. User-owned files
and immutable accepted checkouts are preserved.

No upstream app, static cudart, signed relaxed loads, general alias/extent safety,
shared/barrier/async support, supported-host qualification, AMD, NVIDIA parity or
performance claim is added. The historical52-case clean lane was not rerun or
extended. Continue by applying the widened producer path to pinned external CUDA
samples and selecting the next real first-failure, while retaining the broader
parallel execution and library roadmap.
