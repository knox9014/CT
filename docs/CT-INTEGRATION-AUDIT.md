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
  repository lock. Hosted CI remains not_run until actually dispatched.

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
must be verified independently below.

- Clean-candidate results will be recorded against their exact commit below;
  source-equivalent documentation commits must not relabel that test commit.
- Historical baseline DLLs are preserved local negative-control artifacts.
  Their actual binary/hash-record bytes are included in native configuration
  identities; their original build source revisions have not been independently
  reconstructed. Do not call these public-source reproducible baseline builds.
- The tracked PR graph uses existing local remote-tracking refs, not a fresh
  GitHub API observation. Remote snapshot is not_run until independently read.
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
