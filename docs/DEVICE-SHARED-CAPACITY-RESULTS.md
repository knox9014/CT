# Device shared capacity results

The product now supports Driver/Runtime device attribute8 with the bounded static
shared-memory capacity: min(native Level Zero maxSharedLocalMemory,16384bytes).
This is an ordinary CT feature, with no test metadata injection. Driver46 and
Runtime40 exports are unchanged.

Each translated entry retains its conservative aligned static-shared requirement.
Before native module creation, the Driver checks every selected entry against
the owning context device's capacity. Independent entries are checked separately.
Nonzero dynamic-shared launch arguments remain unsupported.

Four new Rust tests cover zero/small/exact/large/maximum-u32 native capacities,
alignment padding, all-entry checks without summing independent entries,
16384-byte boundaries, rejection before invoking the native creator, and
preservation of its ordinary error. Runtime forwarding includes attribute8;
attribute9 replaces the old unsupported8 preflight control.

## Native attribute ABI evidence

On2026-10-27, the official-header ABI consumer returns
`[1024,1024,1024,1024,2147483647,2147483647,2147483647,16384,0]`
for attributes1..8/20 on the local Intel device. Driver and Runtime values agree;
guard words, output preservation, TLS errors and unchanged context checks pass.
Both full and minimal owned-module Driver providers pass. Missing, forwarded and
absent optional providers each produce loader error35 as required.

Private source-bound attribute record:
`.cache/runtime-attribute-runs/10c832be1ac5432c84a044ac7ca6e0f2/manifest.json`.
Source fingerprint:
`a3c6a9f7f023120f401827aa1eba1b9f47fba124c816e3f6120d4a601a109b6c`.

Python219 tests pass. Rust workspace199 pass/4 existing ignored; Runtime129 pass.
Clippy with warnings denied and formatting checks pass. Independent read-only
review found no integration blocker. A stale test-name contract reference was
detected by full tests and corrected before accepted evidence capture.

## Frozen full capture and replay

All parent native regressions pass: owned streams, host storage, queued copies,
Driver/Runtime events, no-collector profiling, barriers, static shared arrays,
uniform control flow and fused arithmetic. Actual pinned SPIR-V validation and
original vectorAdd capture/replay pass. Original matrix kernels execute with
their per-entry requirements retained and checked by the new product code.

The unchanged original matrixMul EXE again passes both small positive geometries
under the test-only metadata shim, with7168 finite exact output words. No-launch
and no-HtoD controls still expose the upstream NaN false-PASS and are externally
rejected. Fresh-process replay repeats all five modes and matches raw arrays,
metadata and traces. The ordinary baseline still exits1 at attribute75/801.

- Full capture: same private folder, `matrix-runtime-manifest.json`.
- Capture SHA256: `333a77216e0641edfa6f1297e16438c673e58e25028d8b900a6aa85a3caaffbe`.
- Attribute manifest SHA256: `56704ba173c15e5302dbf6f1df61729fd2f99875ce34c182edfb90b5dc7a4f0c`.
- Fresh replay: same folder, `matrix-runtime-replay-fb67d8c982d742a0b8558793db34df7e.json`.

Source fingerprint and all provider/EXE/PTX identities are bound to these records.
No personal data or raw logs were uploaded; protected11 files are unchanged.

## Boundaries

This adds truthful capacity reporting and pre-native rejection. It does not
resolve matrixMul's ordinary compute-capability75/76 query. The application
diagnostic still uses explicit test-only injected metadata. Fatbin selection
still chooses its highest-ranked supported candidate before checking capacity;
no smaller-candidate fallback is implemented. A native compiler can report
ordinary resource errors within the conservative declaration budget. Native
execution exactly at the16384-byte declaration boundary is not separately
established by the attribute consumer; actual shared kernels are covered by the
parent native diagnostics. No performance or universal compatibility claim.

See [device policy](DEVICE-CAPABILITY-POLICY.md) and
[implementation plan](superpowers/plans/2026-10-27-device-shared-capacity.md).
