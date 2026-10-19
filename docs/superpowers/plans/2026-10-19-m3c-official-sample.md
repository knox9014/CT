# M3c Official CUDA Sample Test and Adjustment Plan

> Execute inline with test-first changes, systematic failure diagnosis and independent final review.

**Goal:** Test NVIDIA CUDA Samples v12.0 vectorAddDrv with unchanged upstream host/kernel source, adjust CT for observed requirements, and distinguish the adjusted PTX packaging from genuine fatbin support.

**Spec:** `docs/CUDA-CONNECTION.md`; user explicitly requested testing and adjusting CT as far as practical. Keep private files/logs/binaries/vendor downloads ignored; never replace system drivers.

## Observed external requirements

- Upstream commit `2b689228b746248b7bb7d2778d5ea0701669f7d3`, Samples/0_Introduction/vectorAddDrv. Host default N=50000; explicit `--device=0` avoids NVIDIA-specific performance heuristics but still queries compute mode.
- Compile unchanged host against official CUDA 12.0 headers with MSVC. Generate an import library matching ordinary CUDA symbols; executable bytes stay fixed during CT iteration. No host/helper source patching.
- Compile unchanged kernel with official NVIDIA NVRTC12.0.76, compute_52 and C++11. Output is PTX8.0/sm_52 with unannotated u64 pointer parameters, mad.lo.s32, setp.ge.s32, mul.wide.s32, add.s64 and unreferenced module globals.
- The upstream host expects a file named vectorAdd_kernel64.fatbin but passes its bytes to cuModuleLoadData. For this adjusted test supply compiler-produced PTX text under that expected filename. Report this packaging adjustment explicitly; no claim of original fatbin or NVIDIA-original comparison.

## CT changes and constraints

- Accept exactly the additional PTX8.0/sm_52 profile. Validate limited module-global declarations (.global .align8 .u64 scalar, .b8 fixed arrays); references remain rejected. No name/hash-specific replacement or skipping arbitrary directives.
- Accept unannotated u64 parameters only with conservative proof: each parameter-load register has a single definition, is used, and every use is cvta.to.global.u64. Otherwise reject ambiguity; never silently treat scalar u64 as pointer.
- Implement signed s32 compare/mul.wide, with correct sign extension, plus modulo-equivalent mad.lo.s32 and add.s64. Signed comparisons interpret bits, not unsigned ordering. Cover negative and high-bit values independently of the sample's positive indices.
- Report compute-mode DEFAULT=0 because CT does not implement exclusive/prohibited mode; keep NVIDIA compute capability and performance attributes unsupported.
- Extend explicit PTX asset staging to a .fatbin filename only when the payload is ASCII PTX text; retain rejection of actual binary fatbins and collisions.

## Tasks

- [x] Compile upstream host and reproduce current import/attribute/PTX failures. Preserve original executable/source/compiled-PTX hashes.
- [x] Add failing parser/translation tests, implement precise grammar/pointer proof/signed operations and failing compute-mode/staging regressions before fixes.
- [x] Build a reproducible local-cache harness with pinned/hash-checked official source/runtime/NVRTC artifacts, compile original kernel, run unchanged host through CT and assert its success marker and original hashes.
- [x] Independently verify generated PTX outputs/guards and signed edge cases on GPU; regress prior milestones and run independent review.
- [ ] Record adjustments, actual results and unresolved original-fatbin/external-app/NVIDIA/AMD limits, scan publication and create stacked draft PR.

## Execution ledger

- Original host compiled but failed compute-mode query with error0801 against prior CT. The same executable SHA-256 `a3bde451e36d8faa95ea36155cc0799855cee7024fa238f2c15935d5d0f66dff` passed 50,000 elements after CT changes. Host/helper/kernel sources were not patched.
- Profile/unused-global parser tests and fatbin-filename staging test failed before implementation. A separate u64 equality test failed before adding that supported comparison. All are now green.
- Actual NVRTC output was accepted unchanged. Fresh full smoke rebuild passed with identical PTX hash; independent14cases50970outputs896guards including8signededgecases passed.
- All19Rust tests,14Python tests, formatting/clippy and M1/M2/M3a/M3b native regressions passed. Independent reviewer reran profile/codegen/loader checks and all14GPUcases, with no correctness findings.
- Reviewer requested exact ignored-dependency acquisition commands. Added clone/sparse-checkout and allthreewheel downloads to M3c results.
- Ruling: provide PTX text under the sample's expected fatbin filename — original host accepts module bytes through cuModuleLoadData — does not claim actual binary-fatbin support. This is an explicit artifact/build adjustment.
- Ruling: add bounded unused-global declarations and conservative address-use proof instead of rewriting compiler PTX — preserves semantics and rejects ambiguous uses — costs a narrow supported profile.
- Ruling: acquire the matching compiler-header wheel for missing crt/host_defines.h; use only its headers. Explicitly preload same-package NVRTC builtin DLL so compilation resolves its verified dependency.
