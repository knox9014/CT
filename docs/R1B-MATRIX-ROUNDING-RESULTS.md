# R1b: rounding-sensitive original matrix inputs

Status: R1b completed2026-10-28. Implementation, independent review, clean CPU qualification and fresh Intel capture/separate replay passed. This is a bounded R1 numerical extension, not complete R1 or arbitrary floating-point qualification.

## Fixed numerical contract

Original matrix PTX and its ascending-K `fma.rn.f32` accumulator chains are unchanged. Two full-tile cases(tile,M,K,N)=(16,16,16,16),(32,32,64,32) use seeds193,194,295,296. Even seeds produce signed nonuniform decimal-ratio inputs converted to binary32. Odd seeds preserve a signed2^-46 FMA residual that becomes zero if multiplication and addition are rounded separately. Tail products are zero, with seed-dependent inactive inputs; this discriminator is distinct from general decimal workload diversity.

Every stored binary32 input is a dyadic number. The extension concerns input conversion and accumulation that require rounding, unlike R1a's exactly representable integer/128 accumulations. The high-precision reference uses the stored binary32 inputs; it does not measure error relative to unrounded real decimal fractions.

Two requirements were fixed before GPU execution:

1. Sequential binary32 FMA RN-even semantics must match the existing integer IEEE oracle at every final output bit:0ULP tolerance, finite outputs and exact zero sign. Selected complete dot sequences are independently recomputed using Fraction arithmetic and rational RN-even candidate selection. Binary64 only locates candidate neighbours; exact rational distances choose the result and resolve ties.
2. For every cell, the absolute error from the exact real dot of binary32 inputs must be <= gamma_K * sum(abs(A_j*B_j)), where u=2^-24 and gamma_K=K/(2^24-K). The real-dot bound does not replace the strict FMA-bit check. A deliberately split residual result0 can satisfy this looser bound yet must fail the bit check.

Recipes stay in a closed normal/zero range. Nonzero general input products lie on a lattice no finer than2^-56, and magnitudes remain bounded well below overflow. The reference explicitly rejects subnormal or nonfinite intermediates. This does not qualify arbitrary subnormals, FTZ/DAZ behavior, overflow, NaN propagation, approximate arithmetic or alternate accumulation orders.

All A/B bytes must be preserved, C starts NaN, and all three buffers have16 guard words on each side. Schema3 and `--rounding-v1` are explicit. Baseline and breadth worker flags/schemas remain unchanged; unknown/conflicting profiles are rejected. Four positive workers cover8 input/geometry combinations and5120 outputs per pass. Four no-launch/no-copy controls cover8 additional jobs.

## Fixed source and CPU evidence

Product fingerprint: `cdf9140a1d83f4f86dbc15729bfc59cba8cfba859a6a45a290b1d8ad749eabce`.

Private checkpoint commit: `f80499350a5b1344b16ffcc6e9a9fde11e598e82`; Git tree: `5d509b71d5178ff21351b9fae436ea8af56a1b00`; file-map SHA256: `2fadd947aa735cb82c2455ae918d1d82b317520017a3b87a3441406c84934d33`. Its582 source files exclude ignored SDKs, original cache and generated evidence. Installed host tools/dependency caches remain prerequisites; this is local reproduction, not another-machine or network-independent installation proof.

Clean CPU lane:11/11 passed, Rust207/4 existing ignored, Runtime129, Python252. The10 rounding tests cover rational anchors/ties, cache type isolation, FMA-vs-split discrimination, exact real-dot bounds, corrupted/nonfinite outputs, closed profiles/schema/commands and run/profile/ULP drift. Previous breadth8 and baseline10 focused tests also passed. Independent read-only review found no actionable issue in the reviewed scope and confirmed the original PTX's accumulation order.

The tested checkpoint predates result/plan reporting edits. Its full-tree identity refers to that fixed source point; ordinary documentation edits afterward do not change the product fingerprint. Original index/HEAD and protected11 byte hashes are checked at final acceptance. No root stage/commit/push or upload is authorized by these local records.

## Intel acceptance

Fresh parent existing-app/R1a capture passed under the same frozen source, including11 ABI/8 app cases and the42 exact-input breadth combinations. All8 rounding observations passed their defined expectations:8 positive input/geometry combinations,5120 exact FMA output words,768 positive guard words and8 omitted-operation jobs correctly rejected numerically after API completion. A separate replay reexecuted all8 observations in new processes and matched every raw observation hash. Replay is reproducibility evidence, not added input diversity.

All5120 outputs also satisfy the exact Fraction real-dot bound. Maximum absolute real-dot error is3713133439/9007199254740992 (approximately4.122406237483389e-7); the maximum fraction of the individual cell budget is16224777993525/167247318518119 (approximately9.7011%). These maxima need not occur at the same cell.2560 actual residual outputs retain magnitude2^-46, discriminating fused from split arithmetic. The0ULP and gamma_K policies were unchanged after execution.

Capture SHA256: `6ea3b4bd7dbbed85879a2c34716fb9c30f739fc4d6f3f06673dce89572bc7fc9`. Replay SHA256: `95b5f5751f3d823cf74dafe664d564278394441fc24353ddba6c6db0bd3baba6`. Raw evidence stays ignored; the final source/CPU/artifact/numerical/privacy/protected-file cross-check is recorded in `.cache/r1b-final-verification.json`.

## Remaining work

Long resource lifetime/concurrency/error cleanup, broader original EXE shapes, actual useful-app first-blocker qualification, other Intel PCs, performance and AMD remain unfinished. Whole R1 is not complete.
