# Experimental virtual PTX target proposal

Status: historical proposal before implementation. Current implementation and
bounded evidence are tracked in [virtual target results](../../VIRTUAL-TARGET-RESULTS.md).
Strict/default queries still return801; the explicitly enabled experimental
product target is a separate qualified path.

A bounded software target can be coherent without complete NVIDIA hardware
coverage if its semantics and limitations are explicit. Proposed name:
`ct-sm52-subset-v1`. An explicit process-fixed opt-in would map major/minor to5.2
as a virtual selection target, while preserving the actual Intel device identity.
Default behavior remains strict. A flag merely moving the old test injection into
product code is not sufficient.

Required contract:

- One consistent, immutable process policy for Driver and Runtime metadata and
  selection. Define authority, initialization order, configuration drift and
  missing/foreign-provider handling before implementation.
- Machine-readable exact supported PTX pairs, APIs, operations, resource limits
  and unsupported code kinds; no NVIDIA conformance or full architecture claim.
- Unsupported and late-registered kernels fail closed. Native errors propagate.
- Native-derived resource limits stay bounded; NVIDIA SM-count/clock ranking
  remains unsupported. First useful scope is explicit device selection.
- Validate the actual product path without test metadata DLLs using the pinned
  original EXE, full finite numerical checking, omission controls and replay.
  Default rejection and invalid/changed configuration controls are required.
- Report virtual target selection separately from physical hardware identity
  and from general application/release compatibility.

Open engineering issue: current strict Runtime attribute preflight can reject75/76
without loading Driver. An opt-in must preserve a well-defined default precedence
while guaranteeing that separately loaded Driver/Runtime modules cannot silently
latch different policies. Resolve this explicitly rather than reading an
environment variable independently on every query.

Current version queries also remain unsupported (write0/return801);12000 is the
resolver lookup ceiling, not a successful Driver/Runtime version report. It is
not precedent for advertising an architecture.

This proposal is the next device-selection design task after capacity-aware
fatbin selection. It changes no current export count, query result or application
qualification.
