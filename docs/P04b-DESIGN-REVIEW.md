# P04b symbol API design review

Read-only independent review found coherent architecture and five P2 contract gaps:
single-lease handoff, combined-error precedence, pending/frozen/failed duplicate
lookup, raw native copy error handling, and D2D ownership coverage. The design and
plan now specify each before implementation. A P3 interface/test precision item
was included during plan completion (exact shared methods, reserved binding vector,
query/load counts, late-validation publication and native pointer overflow).

The pinned original CUDA12 header explicitly preserves query outputs on invalid
symbol; the chosen CT policy preserves all error outputs. Direction/range precedence
is explicitly CT policy, not inferred NVIDIA behavior. No second loader/module cache,
new Driver export, broader global type, async/UVA or framework support is implied.

This is design review only, not Runtime26 implementation or native certification.
The accepted P04a code/result remains its existing pinned48-case candidate.

## Original-header feasibility result

The pinned, authenticated CUDA12 headers compiled the four exact function-pointer
type assertions and enum assertions with MSVC /W4 /WX. The CPU-only probe returned
`SYMBOL_ABI 4 8 8 4` (four signatures; 8-byte pointer/size_t; 4-byte copy enum).
This did not link or load CT and did not execute a GPU. Private compiler output and
producer identities remain under ignored .cache/p04b-execution/abi-feasibility/.
All11 preserved user files still match their pre-existing SHA256 values.
