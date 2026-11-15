# R1a: exact original-matrix input breadth

Status: R1a completed2026-10-28. Implementation, clean CPU validation and fresh Intel capture/separate replay passed. This is one bounded part of R1, not completion of R1 or general CUDA support.

## Implemented scope

The original pinned matrixMul PTX and entry bodies are unchanged. A separate Driver consumer now supports seven closed full-tile jobs(tile,M,K,N): the original four plus(32,32,96,64),(32,96,32,64),(32,64,128,32). The added cases exercise non-square dimensions and up to four K-loop tiles. Partial tiles and arbitrary shapes remain rejected before launch.

The breadth contract uses six fixed seeds193,194,195,296,297,298: two input pairs for each of mixed signed, asymmetric and exact pair-cancellation recipes. A is integer/8 and B integer/16, with absolute coefficients<=9 and K<=128. Every product and FMA intermediate is an integer/128 with numerator bounded by10368, so these results require no floating-point tolerance or subnormal handling. Fraction-based CPU tests independently check selected dot products; GPU acceptance compares every output bit against the integer-dot oracle.

Each positive checks entire A/B preservation, C and16-word guards on both sides of all three buffers. C begins as NaN. No-launch/no-copy controls must complete the API path while failing numerical acceptance with the specific omission signature. CPU mutations also reject single-bit output/input/guard corruption, dropped/reordered/relabelled runs, wrong worker command/schema, source drift, parent hash drift, provider identity drift and changed provider bytes.

Baseline schema1 and the original worker behavior remain the default. Breadth requires explicit `--breadth-v1` and job schema2. It is a controlled input consumer of original PTX; the original EXE does not acquire these nonuniform inputs. Existing EXE/Runtime application evidence is captured separately by the fresh parent chain.

## Fixed source and CPU evidence

Frozen product fingerprint: `c0463862f4405920490b044f7bbfe1667d41f135fabdee75197f72c1bb1020d1`.

Private source checkpoint commit: `3a8ec8d9cfbcdcc8c1f86b8fee786be308ce54cd`; Git tree: `708fc775d295f0cf44d9e87d02389cb2672fa250`; file-map SHA256: `353bfd9fd7302433a437444a65f5097c94acc71e1686ddd16a98dab7b48afec1`. Its577 reviewed source files exclude SDKs, original caches, binaries and raw evidence. The local clean CPU lane passed11/11 cases, including Rust207(4 existing ignored), Runtime129 and Python242. Installed host tools/dependency caches were available; this is not another-machine or network-independent installation proof.

Independent read-only review found no remaining actionable issue after adding parent/provider/byte-drift mutation tests. The8 breadth and10 baseline focused tests passed. This is a scoped correctness review, not an exhaustive security audit.

This checkpoint predates result/plan reporting edits. Full-tree identities describe that fixed checkpoint; the product fingerprint remains identical after ordinary documentation changes. No root stage/commit/push or upload is part of R1a. Protected11 byte hashes and original index are checked at acceptance.

## Intel acceptance

The fresh full parent chain passed, including SPIR-V validation, vectorAdd, original baseline matrix kernels and the experimental virtual-target application's11 ABI/8 app cases. This parent's existing EXE shapes are unchanged.

All10 breadth observations passed their defined expectations:6 positive seeds x7 shapes=42 input/geometry combinations,118272 exact output words and4032 positive guard words per pass. The4 omission controls cover28 additional kernel jobs; all API reports completed, while all numerical results were correctly rejected with the expected no-launch/no-copy signature. A separate replay reexecuted all10 observations in fresh processes, matching every stored observation hash, including all buffers and device/API reports. Repeated replay is not additional input diversity.

Capture SHA256: `4f1578f6784032a1900f08f191b33e1367c66080148c3190515b1ec17006a715`. Exact replay/parent hashes, checkpoint/report identities, privacy/protected-file checks and reporting-only documentation differences are recorded locally in `.cache/r1a-final-verification.json`. Raw logs and generated binaries remain ignored and unpublished.

## Remaining work

Still unfinished in R1: broader original EXE shapes, non-dyadic FMA/error budgets, longer resource-lifetime/concurrency/error-cleanup tests. R2 useful-app selection and first-blocker qualification remain separate. Performance, general CUDA compatibility, other Intel machines and AMD are unqualified.
