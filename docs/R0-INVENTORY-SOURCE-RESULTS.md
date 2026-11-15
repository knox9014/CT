# R0: inventory, privacy and private source checkpoint

R0 is complete within its bounded acceptance scope: inventory alignment, actual working-tree privacy scanning, a clean local source checkpoint and fresh Intel capture/replay. No publication or root commit is part of this step.

Finalization date:2026-10-28 (Asia/Seoul).

## Implemented

- Reconciled broad Runtime/logical-stream declarations as experimental/partial; Driver streams remain unsupported. Added the bounded virtual-target declaration without a NVIDIA conformance claim.
- Pinned historical vectorAdd/matrixMul artifact-role hashes and upstream revision without replacing the earlier source identity. See [baseline scope](APPLICATION-BASELINES-2026-10-27.md).
- Added actual working-tree byte inspection for modified tracked and nonignored untracked files; CPU publication validation now uses it. Staged/index/history modes remain available.
- Added a private raw-byte source checkpoint under ignored local cache. It binds file SHA256 values, product fingerprint and a separate generated Git tree/commit, without staging or committing the original repository.
- Independent read-only review found one inspection-order issue: fingerprinting preceded link rejection. A regression test failed first, then passed after moving link rejection ahead of fingerprinting. No remaining issue was found in the reviewed delta. This was a scoped code review, not an exhaustive security audit.

## Current source checks

Frozen product fingerprint: `98e40bac26c11838c7b4658e930888895163d2d882caad0a5560263c57c8357e`.

- Rust workspace:207 passed,4 existing ignored; separate Runtime:129 passed.
- Python:234 passed, including modified/untracked privacy fixtures, path rejection, scope drift and source-checkpoint tests.
- Formatting, clippy and static profile/coverage checks passed. An initial test build could not overwrite an existing Windows linker output; the same tests passed using a separate target directory. No product code change was needed.
- Protected11 file hashes match. Working-tree pattern scan reported no findings. These checks do not prove arbitrary content contains no personal information.

## Clean local source checkpoint

The first clean checkpoint exposed two old configuration tests reading an ignored producer manifest. They failed with a missing-file error instead of silently inheriting the original cache. The tests now construct synthetic producer fixtures, copy real source/profile inputs, assert the expected SHA256 and verify changed producer bytes alter the bound hash. Independent review and all5 focused gate tests passed. No product runtime or numerical oracle was changed.

The corrected checkpoint contains573 reviewed files. Private generated commit: `6152621709c783fc7879fdf85138f35ebe9c08bc`; Git tree: `83bb9dfd72254cda18cdbbfcb8bce4f87b40a063`; file-map SHA256: `b3c0896994c5c69e2e91c140a5d04dd108fdd838964f5c77fbee2bde54348542`.

Its required CPU lane passed11/11 cases with `clean=true`, including Rust, Runtime, all234 Python tests, formatting, clippy, registry/profile and actual working-tree privacy checks. The checkpoint's Git objects and current bytes verify against its manifest. It excludes the original SDK/cache and generated evidence. Build tools already installed on this PC were used; this does not establish network-independent dependency installation or another-machine reproduction.

The tested checkpoint predates these completion-report edits. Its full-tree identity describes that fixed source point; only ordinary result/plan documentation is finalized afterward. Its product fingerprint remains identical to the current source. Original repository index bytes and protected11 files remain unchanged.

## Fresh Intel acceptance evidence

Capture SHA256: `250c655955976074e5e5a79fa7b05bd79b675e8739f80ce5a161b3785dcc996d`. Separate replay-report SHA256: `044a3e564a9ccbc7e61c44620e5cfb165af392b9a92f54176241d5bfa96f4db4`. Both bind the corrected98e40 product fingerprint, not the superseded intermediate checkpoint.

The full native parent chain passed, including validator-backed translation, upstream vectorAdd capture/replay, unchanged original matrix kernels and bounded Runtime/stream/event diagnostics. The final virtual-target consumer passed11 ABI and8 app cases, then replayed them in separate processes. Matrix shapes(M,K,N) are(32,32,32) and(64,64,96), full tile32 with the original constant inputs. Traced positives check7168 finite exact output words per capture/replay pass. Nominal positives use the original EXE and CT provider DLLs without metadata injection or an observation shim. Noop launch/copy controls still require the external oracle to reject invalid computation despite sample success text. Strict and invalid-policy cases fail as specified.

Historical5a513 inventory references remain unchanged. Runtime40/Driver46 exports, sample execution and a source checkpoint do not establish general CUDA compatibility, hosted CI, another Intel machine, performance qualification or AMD support. Raw captures, manifests and source-candidate CPU reports remain ignored and unpublished. Their final cross-check is recorded locally in `.cache/r0-final-verification.json`.

Next: R1 broadens valid input/numerical/lifetime coverage; R2 pins an actual useful application's dependencies and first blocker. No additional API is selected merely to increase the export count.
