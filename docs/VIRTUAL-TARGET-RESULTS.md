# Experimental virtual target: actual CT product path

CT implements the explicit software target `ct-sm52-subset-v1`. It returns
compute-capability major/minor5/2 for selection purposes while preserving the
actual Intel device name and native-derived resource limits. This is not NVIDIA
hardware identity, full CC5.2 conformance or general CUDA/application compatibility.
Driver46/Runtime40 exports and unsupported version queries0/801 remain unchanged.

## Activation and lifetime

Set `CT_VIRTUAL_TARGET=ct-sm52-subset-v1` in the launched application's environment.
Unset or `strict` selects the default strict mode. Empty, unknown or non-Unicode
values return initialization error1. Driver alone snapshots this at the first
valid cuInit(0) attempt, before native initialization; failure does not reopen the
policy. Nonzero cuInit flags do not consume the latch. Restart the process to
change mode. Runtime delegates queries and never reads this setting itself.

For a PowerShell session, opt in before launching the application:

```powershell
$env:CT_VIRTUAL_TARGET = 'ct-sm52-subset-v1'
```

Unset it for subsequently launched strict-mode processes with
`Remove-Item Env:CT_VIRTUAL_TARGET -ErrorAction SilentlyContinue`.

The executable must use the local CT Driver/Runtime bundle. Setting this variable
alone does not install a system driver or make arbitrary CUDA applications work.
Automatic NVIDIA-style SM/clock performance ranking remains unsupported; the
qualified original sample uses explicit `-device=0`.

Runtime75/76 now reach Driver. With a real strict Driver they still return801;
missing/foreign optional binding returns35, positive invalid ordinal101 and
invalid configuration1. This deliberately changes earlier Driver-free CC rejection.
Null1/negative101/other unsupported801 preflight remains Driver-free. Query
outputs, TLS errors and context preservation retain their bounded contracts.

## Verification scope

The official-header native consumer checks strict/virtual modes with both Driver-
first and Runtime-first initialization, subsequent environment mutation, invalid
flags before initialization, persistent invalid/empty/non-Unicode configuration,
physical Intel identity, resource/version/ranking behavior and late Runtime
registration of unsupported code. That late launch returns801 without GPU execution.
Missing, forwarded and absent optional Driver providers each return loader35.
Context preservation is checked during the query phase, before the late launch
creates its ordinary Runtime context.
The two order cases refer to API initialization/first use, not separate physical
DLL image preload orders: this consumer loads Runtime's image first. Policy is
selected only by cuInit, not DLL loading; other image-preload orders are not
separately established by these tests.

Pure Rust tests additionally simulate native initialization failure to prove it
does not reopen the policy. This is not a physical hardware-failure experiment.
Python checks bind exact environment/configuration, commands, provider hashes,
closed artifact sets and scope; metadata-injection DLLs are forbidden in product
bundles. Raw output corruption is rejected even if its recorded hash is updated.

Original matrixMul uses the pinned NVIDIA source and existing adjusted-build
recipe; no source or resulting EXE edits are made between modes. Nominal runs use
CT Driver and Runtime directly with no metadata or observational DLL. Their sample
PASS/completion is recorded separately from traced runs' independent full finite
numerical validation. The observational Driver forwards metadata unchanged;
no-launch/no-copy variants supply API-success NaN controls, not fake success
evidence. Sample PASS alone is never sufficient numerical acceptance.

Frozen capture and fresh-process replay: all11 native ABI cases and8 application
cases pass. Strict/default and
invalid-configuration app controls exit1. Both nominal shapes complete, traced
positives verify7168 finite exact output words and both omission controls are
externally rejected despite sample PASS. Replay matches all traced input/output,
metadata-free trace and ABI report values. Positive externally checked output
comparisons total14336 over capture/replay; nominal completion remains separately
qualified. All parent native regressions, real SPIR-V validation, original
vectorAdd capture/replay and original matrix-kernel capture pass for the same source.

- Private capture: `.cache/runtime-attribute-runs/5573f07e10864e9cbc328c5e8f50250f/virtual-target-manifest.json`.
- Capture SHA256: `7328f76bd16c3aa3457dfea1f25b65c8471b8d7d72e14b8febc0c6715e691b1d`.
- Private replay: same folder, `virtual-target-replay-7dc404ac8c4140bdaa2e36a160bdf3be.json`.
- Extra local CLI smoke: same folder, `virtual-cli-smoke.json`; existing ct.py run
  launches the product without a metadata shim, exits0, empty stderr, sample PASS.
  This CLI smoke is completion evidence, not additional independent numerical data.

Rust207 tests pass/4 existing ignored; Runtime129 pass; Python224 pass; clippy and
format checks pass. Source fingerprint:
`5a513f17ae2aa3453996535e9d5e0a64180ad8c15702190d86c906a129305359`.

The original sample's printed Maxwell label is its own mapping of the virtual5.2
target, not CT changing Intel hardware identity. Other application binaries,
larger matrices, performance, AMD and release readiness are not established.

See [machine-readable contract](compatibility/virtual-target-v1.json),
[device policy](DEVICE-CAPABILITY-POLICY.md) and
[implementation plan](superpowers/plans/2026-10-27-virtual-target-v1.md).
