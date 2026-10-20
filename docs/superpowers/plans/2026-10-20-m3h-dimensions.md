# M3h implementation plan

Spec: [design](../specs/2026-10-20-m3h-dimensions-design.md).
Execution: inline continuation of the authorized P03 work, with one final reviewer.
Use the existing checkout/cache on a dedicated feature branch; preserve baseline
DLL before modifications, never reset other work or merge main.

## Task 1: PTX and SPIR-V components

- [x] Add tests in ct-ptx/tests/dimensions.rs for all12 builtin kind/component pairs
  and illegal suffix/type, and codegen translation.rs for component indices0/1/2
  and one shared global per kind. Run cargo test -p ct-ptx -p ct-codegen-spirv:
  new tests must fail before production edits.
- [x] Value::Builtin(u32,u32) in ct-ptx/src/lib.rs; parser.rs recognizes exactly
  four names and three axes; emit.rs extracts the selected component. Existing
  x-only output semantics remain. Repeat tests and commit this task.

## Task 2: launch dimensions and limits

- [x] Add native pure tests for valid asymmetric shapes, each zero/cap violation,
  oversized block volume, u64 block-product overflow and per-axis U32 overflow.
  Run cargo test -p ct-backend-intel and confirm missing validation fails.
- [x] Device max_groups:[u32;3], capped to I32_MAX, Device::validate_launch;
  new Backend::launch_entry_3d(...,grid:[u32;3],block:[u32;3]); retain old wrappers.
  Validate again at native boundary before mutation. cuLaunchKernel forwards
  arrays after validation; attributes5..7 report consistent grid limits.
  Run workspace tests, rustfmt, Clippy; commit.

## Task 3: native and application evidence

- [x] Synthetic multidimensional.ptx contains coordinate-diagnostic and bounded
  matrix-add entries. Python m3h_dimensions_check.py compares CPU nested-loop
  oracle for all12 registers, unit axes, asymmetric2D/3D and repeated shapes;
  compare baseline rejection, raw/compressed fatbin, output guards and invalid
  launch recovery. Keep assets and logs ignored.
- [x] Independent m3h_cuda_app.c with pinned CUDA headers; run_m3h_smoke.ps1
  builds it and invokes GPU/CLI harness. Verify original bytes, C output and
  guards through public CLI. Verify Rust including native/producer, Python19,
  native ABI and M2/M3c/M3f/M3g affected regressions. Run official validator if
  available; otherwise explicit skip. Record exact executed counts.
- [x] Update results, profile manifest and support docs without marking all P03
  complete. Review, publication/identity scans, commit, push, stacked draft PR,
  attach artifact. No merge.

## Review focus

Check all12 builtin mappings and interface sharing, limits versus advertised
attributes, checked multiplication and no mutation before invalid launch rejection,
legacy wrappers, shape changes on shared kernel handles, per-entry lifetime,
CPU oracle independence, guard coverage, and synthetic versus upstream claims.
Actual driver failure/device loss, AMD/NVIDIA and giant accepted launches are not
covered by the bounded native matrix; never infer those outcomes.
