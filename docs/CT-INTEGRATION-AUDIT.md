# CT universal foundation execution audit

Implementation began 2026-10-20; clean-candidate verification continued 2026-10-21.
Implementation baseline: `d86d916`.
This foundation preserves the Rust CUDA application connection goal. It does not
claim general CUDA, Runtime, framework, AMD, or NVIDIA compatibility.

## Implemented

- Separate coverage/application/tool/corpus registries; existing closed profile-v1
  remains unchanged. All 26 exports and existing feature IDs are inventoried.
  Resolver, behavior, ABI, semantic, native and application evidence stay distinct.
- Official CUDA 12.0.107 header ABI comparison for 26 signatures in separate
  translation units. Explicit four/five-argument resolver PFN mapping; error,
  query and device-attribute values; real official-PFN consumer calls into CT.
- Module exporter with distinct unsupported/invalid/I/O exits, preserved entry
  ABIs, and removal of stale output on failure.
- Official SPIRV-Tools v2025.4 source build, source/dependency archive hashes,
  executable pin, OpenCL 1.2 target, eight positive and two corrupt controls.
- Immutable NVRTC capture/replay with five CT-owned source families, recipes,
  source/recipe/output hashes, and reviewed expectations. Capture is preparation;
  normative replay records each fixture separately.
- CPU/validator/producer/Arc/combined lanes, exact source fingerprint, sanitized
  environment, configuration/case/tool identities, original report bundle checks,
  and a static 18-PR dependency snapshot. No PR is merged by these tools.
- Hosted Windows CPU/validator workflow. Hosted CI execution is not verified by
  local execution; the workflow does not use a personal GPU runner.

## Verified clean candidate

Validated 2026-10-21 at `54e7f1593faace0f041691d1eed17f6bafafd0a2`, with a
clean managed checkout and execution-scope fingerprint
`0ef0ca3ff27edfdf0603f84d1784d5989ff7498ec94f893257ac768b9d3d23a0`.
The original report retains that commit; later documentation commits do not
become directly GPU-tested commits.

| Check | Observed result |
| --- | --- |
| Required combined cases | 26/26 passed |
| CPU Rust | 85 passed; two explicitly ignored cases excluded |
| Rust including prepared ignored cases | 87 passed, including native smoke and real producer parity |
| Python | 58 passed |
| Official validator | Eight accepted fixtures, two corrupt controls rejected |
| NVRTC | Five regenerated output hashes unchanged; two supported translation/validator cases, three expected unsupported controls |
| M3k–M3o Arc regressions | 2,304 cases; 19,372,800 exact results; 295,200 guards |
| Independent CUDA consumers | Official-PFN ABI calls and static/dynamic Driver consumers passed |
| Original bundle audit | Source/config/environment/catalog/tool/input identities matched independent expectations |

The fixed upstream vector-add producer output also translated and validated
unchanged at this candidate. Capture-only results remain `not_run/capture_only`;
the three unsupported controls are semantic diagnostics, not supported features.
Raw candidate reports are preserved under ignored `results/local/`.

The change is published as [stacked draft PR #19](https://github.com/knox9014/CT/pull/19)
on PR #18. Hosted CI outcomes are tracked on that PR; local execution is not
substituted for hosted CI. No merge or ready-state change is performed.

## Correctness defects exposed by actual validation

1. Existing floating operations used Shader-only `NoContraction` in a Kernel
   module. Kernel `ContractionOff` is now emitted for every entry point.
2. Existing signed SPIR-V integer types violated Kernel's Signedness-0 rule.
   Shared integer types now use Signedness 0; signed conversion, comparisons,
   arithmetic shift and wide multiplication retain their explicit signed opcodes.
   Duplicate integer declarations and redundant signed bitcasts were removed.

Both defects were reproduced before correction. The official validator accepts
the corrected outputs; corrupt binaries remain rejected. Native regression
checks confirm the tested signed operations on Arc, rather than treating
validator acceptance as numerical equivalence.

## Local evidence before the clean candidate

All four required local lanes passed against the same recorded dirty-source
fingerprint. These runs include the user's preserved license metadata changes;
they are not a clean-candidate or new-HEAD claim.

- Python: 57 tests; CPU Rust includes the two new module regression tests.
- Official validator: eight accepted fixtures, two rejected corrupt controls;
  separate fixed upstream NVRTC vector-add output accepted unchanged.
- NVRTC sources: `address_control` and `vector_add` translated and validated;
  `scalar`, `multi_entry`, `block_candidate` explicitly unsupported. The three
  negative controls do not count as three supported features or GPU executions.
- Arc: Level Zero/CUDA ABI, explicit native smoke, M3k–M3o regressions, and
  independent static/dynamic CUDA Driver consumers passed.
- Additional direct M3j regression passed after the signed-type correction.
- A fresh independent source build of the validator also passed real controls;
  its separate local executable identity was used, not substituted into the
  repository lock. Hosted execution is tracked separately on PR #19.

## Independent review and corrections

Two implementation reviewers inspected the new foundation and cumulative CUDA
common contracts from `main` (`64ff908`). No new Critical/Important cumulative
ABI/lifetime/failure-containment contradiction was reported in inspected code.
This is bounded review coverage, not a proof that the repository has no defects.

Review fixes include: public recipe paths; observed host platform; exact hashed
NVRTC binding; capture-only status propagation; separate negative controls;
producer translator build; independent required case sets; original lane bundle
checks; independently supplied tool locks and Git cleanliness. Foundation
reports explicitly reject release claims.

## Remaining evidence and scope limits

The first clean candidate, `b079f41`, passed 21 of its 26 combined cases but
failed all five producer replays. Its recipe hashes referred to CRLF bytes in
the original Windows checkout, while Git's corpus attributes checked out LF.
That candidate is not a passing combined result. Recipes are now fixed as LF
bytes, with matching recipe hashes; source and generated PTX hashes are unchanged.
A regression test and the static coverage CLI validate the real repository
corpus, so this is checked before attempting a GPU run. The corrected candidate
subsequently passed the independent clean-checkout run recorded above.

- The validated clean candidate is recorded above. Source-equivalent
  documentation commits must not relabel that test commit.
- Historical baseline DLLs are preserved local negative-control artifacts.
  Their actual binary/hash-record bytes are included in native configuration
  identities; their original build source revisions have not been independently
  reconstructed. Do not call these public-source reproducible baseline builds.
- The initial tracked graph came from local remote-tracking refs. A fresh
  GitHub observation on 2026-10-21 matched all 18 recorded draft heads; that
  observation is bound to the local integration audit. PR #19 is the separately
  identified candidate, avoiding a self-referential head in its own tracked file.
- No original distributed CUDA executable, general cudart/library/framework,
  AMD or NVIDIA GPU compatibility is established by these foundation tests.
- Raw logs, generated PTX/SPIR-V, vendor headers, DLLs, and local bindings stay
  ignored. Existing user Cargo/README/LICENSE changes are excluded from the
  foundation candidate and must remain intact in the original checkout.

## Next implementation inputs

P05 primary-context design can proceed alongside this foundation: retain/release,
active/current context behavior, reset, TLS stacks, shared device state, and
resource invalidation need one common contract plus independent consumers.
P03/P04 should use the preserved scalar/multi-entry producer failures to improve
typed ABI/address analysis without source rewriting. P10 shared/barrier design
must define block participation and failure behavior before promoting the
currently unsupported block producer case. These are general semantic features;
one successful application does not define their scope.
