# P04b native partial symbol read follow-up

2026-10-25: closed the retained P3 coverage gap from [P04b](P04b-RESULTS.md).
No Runtime/Driver implementation or supported API/type range changed.

The genuine nvcc shared-cudart fixture now calls cudaMemcpyFromSymbol with
offset 1/count 2 before each kernel update. Its destination contains 64 bytes
of guard storage on either side. The fixture prints all 130 observed bytes;
the independent Python oracle derives the selected bytes from the expected
symbol value and checks every guard byte. Both contexts perform 100 reads.
No-op expectations retain the same host copy observations while rejecting
incorrect kernel results or modified guards.

Verification performed on this follow-up working tree:

- New oracle test first failed because partial-read observations were absent,
  then passed with the fixture/oracle update. Byte-selection and left/right
  guard corruption are rejected, including the no-op payload control.
- P04b Python tests: 14 passed. Complete Python discovery: 140 passed.
- Rebuilt genuine CUDA host, ABI consumers and CT DLLs; all eight diagnostic
  modes passed, followed by evidence reconstruction and isolated fresh-seed
  native replay (evidence_qualification=true, release_claim=false).
- Independent read-only review of the three changed test files: no actionable
  findings. Reviewer ran four oracle tests; native execution was performed by
  the main verification run.
- Existing 11 user files remained byte-identical. Publication checks passed.

Native-run source fingerprint:
`ed63fcdc75740eddf370f6c7927fd39ad3e925ad88b6c66f48e262822ec6a8e3`.
Diagnostic manifest SHA256:
`7070a6278cc518f80931d4401e363dc01b0022d8a049d9affd3120f972bd9558`.
Raw execution evidence stays in ignored local cache.

This follow-up was executed in the working checkout with preserved user edits,
not the earlier clean validation checkout. The previous clean 50/50 result at
6003b37 remains historical; its full combined lane was not rerun here. This is
additional bounded Arc correctness coverage, not a performance result, general
CUDA compatibility claim, new security scan or release qualification.
