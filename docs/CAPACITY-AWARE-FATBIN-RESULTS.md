# Capacity-aware fatbin selection

CT now selects the highest-ranked validated PTX candidate whose every entry fits
the owning context device's bounded static-shared capacity. This extends the
earlier capacity check to selection itself. Priority stays PTX8.0/sm52 above
PTX7.0/sm50 and does not depend on record order.

Selection still validates every candidate's translation, metadata/profile match,
duplicate profile, global identity and complete entry ABI. Nonfitting candidates
cannot hide malformed, unsupported or conflicting content. Empty/mixed-raw inputs
retain error1; malformed metadata/syntax retains218; no fitting candidate returns
801. Single/raw PTX follows the same capacity rule. Only the selected image goes
to native creation, with the final capacity gate preserved. Ordinary native
compiler/resource failures propagate without trying another variant. Matching
entry ABI is not proof that alternative trusted kernel bodies compute the same
thing.

Five new Rust tests cover record order, exact/aligned/zero capacities,8KiB/16KiB
boundaries, full per-entry requirements without adding independent budgets,
selected SPIR-V equality to direct translation of the expected candidate, raw
input, no-fit and invalid alternatives. Three tests failed against the previous
selection behavior before the fit filter was implemented. Existing image tests
remain passing. Independent read-only review found no blockers; a requested
malformed-syntax218 case was added and passes.

## Evidence scope

The lower-capacity selection branch is exercised with synthetic device limits in
the real Rust selector. No physical low-shared-capacity GPU is available in this
run. The local Intel device reports CT's full16KiB bound, so native regression
results must not be presented as execution of physical low-capacity fallback.

Rust workspace204 tests pass/4 existing ignored, Runtime129 pass, Python219 pass.
Clippy with warnings denied and format checks pass. Source fingerprint:
`07c6229903afb25b99e66babaa0cf3685e2b0e65eaf653d111fa4239e24445c1`.

## Frozen native regression capture and replay

Fresh owned-stream/host/queued-copy/event/profiler/barrier/static-shared/uniform/FMA
diagnostics pass. Actual pinned SPIR-V validation, original vectorAdd capture and
replay, and original matrix-kernel capture pass for this source. The
metadata-injected original matrixMul EXE verifies7168 finite exact output words
across two shapes; API-success no-launch/no-HtoD controls remain numerically
rejected. Fresh-process replay repeats all five app modes and matches raw arrays,
metadata and trace hashes. Its ordinary default baseline still exits1 at75/801.

- Private capture: `.cache/runtime-attribute-runs/14a2a92be13e474ca16bc83403758779/matrix-runtime-manifest.json`.
- Capture SHA256: `eb4f90530d44e37390da034b2ec6e34855ee992b4a9cb05e0b34c1bf01d82d07`.
- Private replay: same folder, `matrix-runtime-replay-fbeb1fe3cbf14bef9464e9bd92efc453.json`.

These native results cover regressions on the local full-capacity Intel device,
not physical low-capacity fallback. Protected11 files remain unchanged; no raw
logs/personal data were uploaded.

Compute capability75/76 remains unsupported. This selection policy does not
advertise a virtual NVIDIA architecture or remove matrixMul's production device
query blocker. Dynamic shared launch bytes remain unsupported. Driver46/Runtime40
exports are unchanged. See [device policy](DEVICE-CAPABILITY-POLICY.md) and
[plan](superpowers/plans/2026-10-27-capacity-aware-fatbin.md).

An independently reviewed next-step direction is recorded separately in the
[experimental virtual target proposal](superpowers/specs/2026-10-27-virtual-target-proposal.md).
It remains unimplemented and changes none of this result's qualifications.
