# M3h / P03a: multidimensional synchronous launch

Continue the user's general CUDA translator goal and existing draft PR stack.
This is the first P03 slice, based on M3g commit03478d3. Preserve normal CUDA
Driver ABI imports, input bytes, privacy scans and process-local staging.

## Design and scope

Extend the existing parser/codegen/backend path; retain one native module per PTX
module. Accept all twelve scalar `%tid`, `%ntid`, `%ctaid`, `%nctaid` components
`.x/.y/.z` as U32 values, mapped to SPIR-V LocalInvocationId, WorkgroupSize,
WorkgroupId and NumWorkgroups vector components. Change internal Value::Builtin
to carry kind and component explicitly. Share vector globals across components
and entries, and preserve each entry's used-variable interface.

Pass grid/block arrays to a new native launch_entry_3d method. Keep existing
single-dimension launch/launch_entry wrappers for Rust consumers. CUDA's existing
cuLaunchKernel ABI already carries all six dimensions and needs no new export.
Accept only nonzero dimensions within the native device's per-axis counts/sizes,
block volume within maxTotalGroupSize, and grid[i]*block[i] <= U32_MAX on every
axis. Compute block volume with checked u64 arithmetic. Validate before setting
arguments or submitting work. Expose native grid limits through attributes5..7,
capped at I32_MAX consistently with accepted launches; attributes1..4 unchanged.

Keep shared bytes=0, null stream and extra, synchronous execution, current PTX
profiles and Pointer/U32/F32 ABI. Do not add new integer operations, vector or
structure ABI, shared/barrier/warp semantics, stored globals, or device functions.
P03 as a whole remains incomplete after this slice.

## Evidence required

Tests first: all twelve IR kind/component pairs; illegal components/type usage;
SPIR-V component extraction and shared globals; asymmetric dimension caps,
zero axes, block product and checked overflow, per-axis global overflow.
Actual Arc execution must exercise nontrivial y/z in both grid and block,
unit/degenerate axes and nonmultiple logical bounds. A coordinate diagnostic
stores all twelve registers for every launched thread; CPU nested loops provide
the independent oracle. A bounded matrix-add kernel verifies numerical results
and partial blocks. Use raw and genuine compressed fatbin inputs, multiple
entries and successive shapes on the same handles. Check invalid launches leave
output unchanged and later valid launches work. Compare preserved M3g DLL.

Build a separate synthetic C consumer with official pinned CUDA headers and
normal nvcuda imports; exercise public CLI byte preservation. Run workspace,
Python, native ABI and affected previous GPU regressions. Official spirv-val,
AMD and NVIDIA execution remain separately reported if unavailable. Perform one
fresh whole-branch review before privacy-safe publication as a stacked draft PR.

## Sources and alternatives

Direct three-axis lowering preserves CUDA coordinates. Flattening launches would
require reconstructing dimensions and could change later block semantics;
per-kernel specializations would not serve the general translator goal.

- [NVIDIA PTX ISA, special registers](https://docs.nvidia.com/cuda/parallel-thread-execution/index.html)
- [Level Zero device limits](https://oneapi-src.github.io/level-zero-spec/level-zero/1.18.31/core/api/apis/device.html)
- SPIR-V builtin enumerants follow the existing pinned Khronos header mapping.
