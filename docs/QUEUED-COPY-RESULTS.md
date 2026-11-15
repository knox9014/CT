# Queued memcpy results (2026-10-26)

Implemented actual background cudaMemcpyAsync submission as the bounded Runtime33 contract. Driver41 is unchanged; mandatory Runtime bootstrap15/kernel5 are unchanged. This is working-checkout diagnostic evidence, not release/framework compatibility or a copy/compute overlap benchmark.

## Behavior

Directions1/2/3 (HtoD/DtoH/DtoD), null/default or owned stream. Host sides must be live allocations created by CT Runtime cudaHostAlloc/cudaMallocHost, with matching context and checked extent. Unknown/pageable host storage801; null/overflow/invalid extent/DtoD overlap1; kind0/4 unsupported801, other kinds21. Valid zero bytes still validate direction and stream before a GPU-free no-op. Host data must not be accessed or modified contrary to CUDA lifetime/synchronization requirements.

A bounded256-job channel feeds one lazy worker. Context gates establish submission order; up to128 context nodes over process lifetime cover all fenced operations. Separate pending/error locks and CVs allow worker progress while callers wait. The worker selects the captured context and only calls raw Driver copies; it owns address values and host-use leases, never a returned caller argument stack. One sticky first async error per context is bounded; later accepted jobs for that failed context are skipped/completed, while other contexts can progress. No independent native queues, per-stream GPU concurrency, PTDS or UVA claim.

Runtime host metadata reserves before native allocation, tracks up to1024 live records, and retains use leases until commands finish. Free excludes new acquisition and waits for uses. Native free plus record removal is atomic relative to new allocation, including physical address reuse. Native failures retain the failed record/charge and are not retried. Driver's existing per-context128/256MiB native allocation budget also remains.

Kernel launch, symbols/module retirement, device/stream synchronization, device memory operations and cleanup fence pending context work. Cleanup executes even after a sticky queue error, removes successfully freed resources, then reports an action error preferentially or the prior async error. CPU host-to-host synchronous memcpy keeps its pre-existing caller-managed fast path. Direct external Driver free/module unload/context destruction while Runtime commands are pending remains unsupported; destroy streams before external context teardown.

## Verification

- Runtime112 unit tests passed; workspace tests passed with three pre-existing ignored tests. Runtime/workspace clippy and formatting passed. Python190 tests passed after final source freeze. Current profile/compatibility/coverage static checks passed; static declarations are not execution evidence.
- Deterministic queue tests show submit returns while a controlled worker remains blocked, FIFO execution, independent-context submission/progress, startup/send failure releasing captures, panic completion and skipped later jobs, and cleanup executing despite a sticky error.
- Host-use tests verify extent/context, adjacent allocations, pending-use exclusion and failed-free retention. An integrated Runtime free test blocks a copy, verifies native free has not occurred, releases the copy and then observes cleanup.
- Independent source review found two races: an absent first context node could let a barrier run ungated; and allocation could reuse a freed host address before old metadata removal. Both were reproduced as failing tests, fixed, and passed deterministic interleaving tests. Final read-only review found no further blockers; review itself ran no builds/GPU.
- Official CUDA header native consumer confirms exactly33 Runtime exports and typed call ABI; invalid arguments/zero-copy preflight leave Driver unloaded. Missing Driver returns35.
- A benign one-past device copy is accepted into the queue then rejected by Driver before a GPU command. Synchronization reports1. Host/device/stream cleanup still executes while reporting prior1; direct Driver re-free rejects both addresses, and repeat stream destroy returns400. Caller context is unchanged. This is validation rejection, not induced hardware failure.
- Real nvcc consumer combines Runtime-owned host storage, queued HtoD, immediate host-source free, queued DtoD, kernel, queued DtoH and three completion paths: owned flags0 stream synchronization, flags1 device synchronization and default-stream device-free fence. Python independently checks all96 output words per run. Two fresh inputs passed. No-op launch and no-op copy providers each returned data-failure42, detecting omitted execution.
- Prior attribute five-mode, default-stream three-mode, host six-mode and owned/host nvcc controls passed under the same DLLs as part of the capture chain.
- Four existing default/kernel/symbol/u64 pure ABI consumers were rebuilt and passed. Both symbol widths also passed native retirement after generating their required fatbin assets from existing pinned fixture sources. An initial ad-hoc retirement attempt omitted that asset and was corrected as a harness configuration issue; no product code change was required. Current symbol control stdout gates consistently use33.
- Original pinned upstream vectorAdd source remained unchanged: fresh Runtime33 custom shared-cudart capture and replay passed original application, trace/no-op and independent raw-buffer checks.
- Original matrixMul rebuilt and inspected without execution: missing Runtime names8 to7. Remaining: five event APIs and cudaProfilerStart/Stop. PTX still stops at .shared line32 (four declarations, four barriers,48 FMA occurrences); floating arithmetic and CUDA compute-capability device selection remain separate blockers. It is not runnable yet.
- Eleven pre-existing user-owned files preserved. Publication scans passed; raw logs, vendor files, DLLs and captures remain ignored/local. Nothing uploaded.

An earlier provisional native capture correctly rejected a changed source fingerprint while ABI controls were being migrated. Accepted evidence below comes from the subsequent unchanged-source capture. A reused Windows linker target hit LNK1114; fresh target/native builds and the full Runtime unit run passed without deleting historical artifacts.

## Local evidence

Source fingerprint: `efb8f2f70be30baeab6aa2613ee3984d66c9d7a2d968827ab23170a87d5b9210`.

| Capture | Manifest | SHA-256 |
| --- | --- | --- |
| Queued copy/kernel/control | `.cache/runtime-attribute-runs/feeaf1fee4e5464799e3ad13a96e5539/queued-copy-manifest.json` | `b71aeeb7c83060cd0a83f06c6f64e0d73fa74fe85c72d5733937849264a18878` |
| Upstream vectorAdd | `.cache/upstream-vectoradd-runs/f4308e24f843407a9471cb59074fdc88/manifest.json` | `4ff115930a53d94f76fa08a8096352537c119d4681447453747daa513b30bbfd` |
| MatrixMul offline | `.cache/matrixmul-triage/0f6842fa24a747aeb6b58e2ff880d9d8/manifest.json` | `97a06cc67fbefa20e1e98656945c7d7a5855f0af200af7078b66e7722087cbf0` |

The native folder also holds the chained host/owned-stream/stream/attribute manifests and existing-abi.json. Symbol-retirement input hashes are recorded in that sidecar. Vector replay: replay-fe42bcce60894401b7e50c3a5c80ee5b.json. Reproduce queued diagnostics with `python scripts/run_queued_copy.py` using the previously authenticated local producer cache. Source changes make these captures historical; no clean-release claim.

[Implementation plan](superpowers/plans/2026-10-26-queued-memcpy.md). [Prior host allocation capture](HOST-ALLOCATION-RESULTS.md) describes Runtime32. Next work is real event completion/timing and profiler behavior; shared memory/barriers remain later translator/backend work.
