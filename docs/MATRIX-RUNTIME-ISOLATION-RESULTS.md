# Original matrixMul Runtime isolation

This is a **test-only metadata-injected diagnostic**, not production matrixMul
compatibility or a release. Product attributes75/76 remain unsupported. The
ordinary original EXE still stops at its compute-capability query.

The pinned upstream source is NVIDIA cuda-samples revision
`2b689228b746248b7bb7d2778d5ea0701669f7d3`. The existing diagnostic nvcc recipe
uses CT's import library; source and resulting executable are unchanged between
baseline and injected runs. The sample is therefore an adjusted-build upstream
application, not an arbitrary downloaded NVIDIA binary.

The test Runtime DLL forwards39 exports directly to the real CT Runtime and
intercepts only cudaDeviceGetAttribute. For valid device0, attributes75/76 return
the injected test value5.2 matching the pinned producer's sm52 target. Other
queries and ordinary preflight delegate to CT. The sample's printed Maxwell/CC
label is injected metadata, never Intel hardware identification or proof of full
CC5.2 support. NVIDIA defines CC as an architectural feature set:
[official compute-capability documentation](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/compute-capabilities.html).

The ordinary product does not use these test DLLs. No environment option or
installer path enables the injection. Local bundles are isolated under ignored
`.cache`; no system Driver is replaced.

## Acceptance contract

The explicit command selects device0. Tile32 cases use(M,K,N)=(32,32,32) and
(64,64,96). All dimensions are complete tiles. The original application uses
its own host allocation, nonblocking stream, asynchronous copies, CUDA events,
one warmup and300 timed launches, final copy and synchronization, host/device
frees and event destruction. The upstream sample does not explicitly destroy
its stream; each diagnostic runs in a separate process.

The observational Driver records the original two host input arrays, entire
device output and a closed call-count trace. Every device allocation is poisoned
with NaN first. The wrapper does not calculate expected output. Python independently
checks every input word against the original recipe and every output word for
finiteness and exact binary32 agreement. Since A=1 and B=binary32(0.01), each FMA
is an independently rounded addition of B; the external oracle repeats this K
times. The earlier original-kernel harness separately covers varied inputs.

API-success no-launch and no-HtoD controls must complete the same application
path but produce the specific NaN omission signature. Original PASS text alone
does not count: its relative-error comparison can accept NaN. Both controls
must be rejected by the external numerical checker.

Capture and audit bind the full source fingerprint, pinned source/EXE/PTX, real
validator evidence before GPU execution, parent regressions, all provider DLLs,
exact command, input/output/trace hashes and exit status. Replay uses fresh
processes/bundles and compares raw arrays, metadata and trace hashes. Performance
stdout is retained privately but not compared or presented as a benchmark.

## Frozen acceptance — 2026-10-27

Fresh capture and fresh-process replay pass on Intel(R) Arc(TM) B390 GPU.
All parent native regressions, real SPIR-V validation, original vectorAdd
capture/replay and original matrix-kernel capture pass for the same source.

| Mode | Shape(M,K,N) | App exit | External numerical result |
| --- | --- | --- | --- |
| Ordinary CT baseline |32,32,32|1|Not reached: attribute75 returns801|
| Injected positive |32,32,32|0|All1024 finite words exact|
| Injected positive |64,64,96|0|All6144 finite words exact|
| Injected no-launch |64,64,96|0/PASS|Rejected: all6144 words retain canonical NaN poison|
| Injected no-HtoD |64,64,96|0/PASS|Rejected: all6144 words NaN|

Each injected run observes3allocations,2uploads attempted,301launches attempted,
1download and3frees. The no-launch variant forwards0launches; no-HtoD forwards0
uploads. Positive variants forward all operations. Replay repeats all five modes
and matches every raw input/output, trace and metadata hash (timing stdout is
deliberately excluded from equality). Positive output checks total14336 across
capture and replay. This is correctness evidence for these small shapes and
constant upstream inputs, not application performance or general CUDA coverage.

- Source fingerprint: `61c2cb1a173567bfb5d5b0b9200f9ef74999de5a041fd3b855d26cedc603c001`
- Private capture: `.cache/runtime-attribute-runs/7f95486aca554783bfe418337cb47efc/matrix-runtime-manifest.json`
- Capture SHA256: `08cdd2eb0c95fbcfbc3a2a52c57f38e29a74582028c45d70be058a6f61b078c0`
- Private replay: same folder, `matrix-runtime-replay-f61596581f444a76a83bd1b527288a62.json`
- Exact EXE SHA256: `bf0f1996767503d6b72901d81828b11af04fb54d4627bf1d84589233ff89e76a`
- Python219 passed; Rust workspace195 passed/4 existing ignored; Runtime129 passed.
- Independent review found a parent-Runtime artifact overwrite; it was corrected
  by keeping the diagnostic Runtime under a separate filename. Final review found
  no remaining blocker; fresh capture/replay verify the corrected identities.

The next production milestone is a defensible device-selection/capability policy
and execution without metadata injection. Keep that separate from adding more
PTX/runtime coverage. Full NVIDIA CC5.2 support, automatic NVIDIA SM/clock ranking,
unmodified downloaded binaries, AMD execution and practical performance remain
unproven by this diagnostic.
