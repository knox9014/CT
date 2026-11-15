# R2u: checked software-target maximum topology count

CT Driver and CT Runtime now support attribute16 only under the existing explicit `ct-sm52-subset-v1` policy. The value is a CT software-target topology count: checked positive `max_slices * max_subslices_per_slice`, fitting a signed32-bit integer. Strict mode still returns801. Zero dimensions, multiplication overflow and products above `i32::MAX` return801, without clamping or manufacturing1. Raw dimensions are retained unchanged in the Intel backend and do not cause enumeration failure; conversion belongs to CUDA policy.

The [Level Zero device-properties specification](https://oneapi-src.github.io/level-zero-spec/level-zero/latest/core/api/apis/device.html#ze-device-properties-t) describes these dimensions as maximum counts. The [Intel Xe architecture guide](https://www.intel.com/content/www/us/en/docs/oneapi/optimization-guide-gpu/2025-2/intel-xe-gpu-architecture.html) demonstrates slice/subslice topology and distinguishes it from execution-unit/vector-engine counts. This mapping is not an active NVIDIA SM count, Intel EU count, occupancy model, architecture-conformance statement or performance ranking.

## Actual qualification

An independently compiled official CUDA/LevelZero-header consumer queried the system LevelZero loader, required exactly one Intel GPU, matched the CT device count/name and verified stable native handles/UUID internally before and after metadata queries. UUID values are never printed. Intel(R) Arc(TM) B390 GPU reported maximum dimensions2 and6; the explicit CT target returned12 through both Driver and CT Runtime. Strict16 remained801/output0 in Driver and801/unchanged output in Runtime. The positive maximum-topology control is independent of CUDA's returned16 value.

All25 fresh native processes passed: five existing attribute/loader controls, nine topology controls and eleven existing virtual-policy ABI controls. Coverage includes Runtime-first/Driver-first initialization, minimal owned binding, absent/missing/forwarded optional binding35, null/invalid-ordinal precedence, canaries, sticky TLS errors, unchanged current context for metadata queries, immutable policy after environment changes, invalid/empty/non-Unicode configuration and late unsupported-kernel refusal. Metadata queries do not acquire a CUDA context. Late-code checks are separate policy regressions; they are not a new application qualification.

The clean immutable CPU lane passed11/11: Python378, Rust225 passed/7 ignored, CT Runtime129 passed, formatting/Clippy, profiles, registry and publication. New CPU checks cover raw zero/overflow dimensions surviving full fake backend enumeration, exacti32 boundary, u32 overflow, strict rejection, and16 forwarding to a deliberately different Driver device handle. Runtime output/error/context rules remain intact. Independent pre-native review required an explicit parent-role check in saved validation; a matching-hash wrong-role regression went RED then GREEN.

Immutable candidate: `463625ba6d184920884b6c1406df2c6d`.
Private source commit: `1cdcb9d0935943686e11977cb3c5a6e659c61955`.
Source fingerprint: `b4aad661a003b7fbe33a55b7aa284a137daea222d6e0503f42c6ff57edf363a8`.
Fresh ABI run: `ea188110ce1d430580034bda322dbb76`.
Topology manifest SHA256: `32d777eba5bda4123fdd8f8f444bae376c348b4256264652e3d7b20494bc2ed8`.
The saved consistency audit passed without another GPU run. Root HEAD/index/protected11 and managed worktrees remain preserved; raw logs, paths and binaries stay ignored.

## Boundary and retention

The historical R2t checker intentionally expects16 refusal. Its fresh capture now rejects incompatible source before budget checks/native work, while immutable historical evidence can still be recovered and audited. A new official NVIDIA Runtime prefix beyond16 has not run in this phase. Next add an actual16-success observer/control and discover the next real request; do not predict or fabricate it. General CUDA application/shipping support remains unqualified.

The native entry checks1GiB estimated peak within40GiB cache/30GiB free limits. The dedicated clean-CPU target's547028551 bytes were removed after source/report verification before native execution. The five-process parent reuses one nonincremental Cargo target. The final source, CPU reports and complete ABI run were uploaded as an encrypted private Drive unit; pinned external SDK/compiler tools remain notebook dependencies for compilation. Recovery keys remain notebook-only.

The unit contains1800 files/228967158 logical bytes and18872547 encrypted data bytes in one volume, with zero exclusions. All five transferred data/helper/guide files were checked owner-only, read back by SHA256 and fully restored. Frozen source verification and the restored25-process saved consistency audit passed. The restoration check did not execute another GPU workload.

Final independent code review found no remaining findings. Cleanup review identified missing ancestor checks on file unlinking and unsafe retry behavior after partial cleanup. The active replacement uses one root/ancestor guard for every removal, exact initial inventories, a durable per-target journal and safe retry that accepts only missing expected files while refusing changed/extra files. Final metadata payloads are saved before removal and applied recoverably. Three private regression tests passed, including a real temporary Windows junction, an interrupted partial-directory removal and preservation of changed bytes. The original cleanup entry is disabled. Reviewers inspected code, not actual keys/proofs/Drive operations.

The final cleanup reclaimed1903 files/410506994 bytes: transfer/restore duplicates, the fully backed142897984-byte ABI Cargo target and compile-only outputs. Combined with earlier CPU-target cleanup, this phase reclaimed957535545 bytes of generated output. Current ABI binaries/observations, source candidates, the small older ABI history, recovery keys and the full warm R2t official Runtime SDK/bridge closure remain local. The ABI target remains recoverable in Drive and surviving local saved audits passed after removal. Cleanup completed its journal, and a repeated invocation correctly reported already_complete.

Measured project cache grew from40199950501 to40286754452 bytes, a net86803951 bytes (about87MB), while adding the qualified topology feature and expanded native evidence. This is a bounded development working set, not global cache eviction or background synchronization. The private recovery catalog now marks R2u as the current ABI run while retaining R2t as the warm official Runtime run.
