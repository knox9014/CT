# P09a2-C: default device-runtime registrations

Status: proposed detailed C design for review. The user approved the basic-then-default
sequence and asked to continue. A/B results are in [P09a2 results](../../P09a2-RESULTS.md).
This document does not claim C implementation, a22-export DLL, or default-build execution.
Implementation stays main-agent inline with independent review, as previously selected.

## 1. Intent and exact producer scope

Let existing CUDA applications use nvcc's default device-runtime linkage without
removing compiler-generated registrations. Preserve EXE/fatbin bytes and connect
through CT's Rust Runtime, the same pinned Driver and Intel Arc. Keep
`--cudart=shared`, non-RDC PTX8.0/sm52 and CUDA12.0.76. Omit `--cudadevrt=none`;
this is default **device-runtime linkage**, not default static-cudart support.

Retain all41 existing required gates. The native-tested product baseline is
bf36cff10a7b66221d339bf49de9f61c5209e9b6; documentation head904e3f7.
Preserve11 original user files, exact-path staging, ignored vendor/log/artifact
storage and publication scans. No AMD/NVIDIA execution or framework/release claim.

## 2. Approaches and grounding

The existing C follow-up already orders bounded metadata handling before full
linking. Builder choice: keep that order. Accept owned, bounded CPU registration
metadata, defer unused native modules, and reject execution that needs unsupported
semantics. Implementing complete CUDA device-runtime/globals/linking now would
expand into P03/P04; retaining the `none` restriction would leave C unaddressed.
A callback that silently discards variables or recognizes private vendor names
would incorrectly report support and is excluded.

A fresh CPU-only observer on2026-10-23 inspected the unchanged earlier diagnostic
EXE (SHA256 b15a2cf27359ffc77961ae8eb0ba950c10ef371b4aceb2bebce76faec4764594).
It exits11 on deliberately unsupported allocation; it proves no CT/GPU execution.
Observed registration: version1 primary608 bytes; version2 own image16 bytes with
zero payload; one raw prelinked image1272488 bytes containing nine kind2 records
and no PTX;32 generated functions and11 variable callbacks. A fresh second
observation confirmed all33 function callbacks (including the user kernel) use
thread_limit=-1, no optional pointers, equal symbol strings and nonnull host identity. Variable flags were
ext=0/constant=0/global=0, sizes4..3048, with equal device-address/name strings.
Raw linked image SHA256 d3afd2189555c658fb84a66ab54c33ebfe85e7f7b028bc8fa425f9a3fce7b570.
These observations guide tests; acceptance must freshly regenerate authenticated
producer artifacts rather than trust this old observer bundle.

## 3. Supported boundary and fail-closed use

Registration acceptance is CPU metadata acceptance, not executability. Version1
keeps its existing strict PTX candidate validation. Version2 accepts an empty or
structurally valid own raw image plus a bounded list of raw fatbin dependencies.
C does not resolve symbols between these images, execute kind2 machine code,
allocate device globals or apply relocations.

A lease may expose a launch image only for a version1 registration with no variable
metadata. All version2 registrations and all registrations containing any variable
metadata return801 before bridge initialization, context selection or native load.
This deliberately also rejects a kernel with an unused global in its own module;
C does not analyze per-kernel global reachability. An unrelated registration stays
usable, even when a different unused registration is non-executable. There are no
symbol-name, producer-name or private device-runtime exceptions.

## 4. Raw image ownership and bounds

New pure decoder API `inspect_container(image:&[u8])->Result<ContainerInfo,Error>`
checks raw header version1/header16, exact declared size, payload8 alignment,
record version0x101, header64..4096 aligned8, nonzero aligned record payload,
checked record extents, at most256 records and kind1/2 only. ContainerInfo holds
record_count:u16, ptx_records:u16, machine_records:u16. Empty raw image16 is
structurally valid here. This API performs no decompression or executable-profile
claim. Existing `extract_candidates` remains strict, including empty/kind2-only801,
PTX8 limits and old flags/options. Malformed outer structure218, unsupported
version/kind/bounds801, detected fallible allocation2.

Version1 still requires extra=null and nonempty strict candidates. Version2 requires
a nonnull extra list and at least one nonnull dependency before its terminator.
Read at most33 pointer slots:32 dependencies followed by a required null. A nonnull
slot32 gives801 before touching its pointee. Entries are **raw image pointers**,
not wrapper pointers. Follow no nested wrapper/list or recursive dependency graph.
Thus pointer cycles cannot cause recursion; a wrapper/list masquerading as a raw
image fails its header check. Identical raw pointer aliases, including an alias of
the primary image, are deduplicated within that registration before copying/charging.
Same bytes at different addresses count separately; cross-registration aliases are
independently copied/charged. Source pointer identities are discarded after copying.

Keep16MiB/image and64MiB aggregate owned raw bytes, including all primary/linked
images across live/retired leases and native ownership. At most33 unique images
per registration. Charge/check every size before creating its full slice or
reserving it, and fail atomically before publishing a token on any error. Keep64
live tokens,1024 lifetime identities,512 functions/token,4096 host function mappings,
1024-byte names,128 native ownership records and64 TLS configurations.

Host pointers must reference readable declared buffers; budgets are not a host
memory probing guarantee. No arbitrary-address recovery is promised. Callbacks
perform no DLL/GPU/JIT/IO/native cleanup or active-work waits.

## 5. Variable callback and state contract

Add exactly one exported ABI:
`void __cudaRegisterVar(void **,char *,char *,const char *,int,size_t,int,int)`
with the existing Windows x64 calling convention. Independently compile the
original pinned host_runtime.h declaration and CT's header, then call the actual
Rust DLL. The two char*/name inputs are owned bounded C strings for the observed
symbol-address form; copy both and require equal contents. hostVar is an opaque
nonnull identity and is never dereferenced. Null/empty/non-ASCII names, null host
or flags outside0/1 give1; unequal valid strings give801. Valid but unimplemented
forms ext=1, constant=1 or global=1 give801. Accept ext=constant=global=0 and
size1..16MiB as metadata only; size0 gives1 and larger sizes801. No storage is
allocated proportional to the declared variable size.

Own both strings and all flag/size fields. Builder-chosen metadata budgets:256
variables/token and2048 live variable mappings across registrations, independent
of function mappings. Reuse1024-byte name cap. Identical same-host/same-record
callback is idempotent; conflicting same-host metadata fails that registration1.
Equal symbols in separate tokens remain independent, with no variable resolver
or address API introduced. Retire releases variable capacities and owned strings.

Use the same Building/Ready/Failed/Retired policy as Function: token state first,
then payload; Failed retains the first code until retire, unknown/retired98,
post-End callback poisons token1. Recheck state under lock after preparation;
concurrent retirement cannot be undone. Successful callbacks preserve previous
Runtime TLS errors. Invalid/budget/allocation callbacks set the first token failure
and return it through later callbacks/End. Unregister remains CPU-only/idempotent.

## 6. Files and shared interfaces

- `crates/ct-fatbin/src/lib.rs` and its `tests/decoding.rs`: pure structural inspection;
  do not weaken candidate extraction or PTX compilation.
- `crates/ct-cudart/src/registration_images.rs`: OwnedImages and bounded unsafe copying.
  `OwnedImages { primary:Vec<u8>, prelinked:Vec<Vec<u8>>, version:u32,
  raw_bytes:usize }`; `unsafe copy_images(wrapper:*const c_void,
  remaining:usize)->Result<OwnedImages,i32>`. Registry serializes aggregate budget
  reservation/publication; Image's Drop releases the aggregate once.
- `registration_variables.rs`: `VariableMetadata { external:i32,size:usize,
  constant:i32,global:i32 }`, owned Variable mapping, pure validation helpers.
  Registry method `unsafe variable(token:Token,host:usize,address:*const u8,
  name:*const u8,metadata:VariableMetadata)->Result<(),i32>` owns state/budgets.
- `registration.rs`: records own variables; Image owns OwnedImages; registration
  checks/publishes all copies atomically. `LaunchLease::image(&self)->Result<&[u8],i32>`
  checks version/variable restriction. Lease snapshots restriction under registry
  lock; previous eligible leases remain valid through retirement.
- `lib.rs`/`kernels.rs`: new callback panic/TLS boundary; preflight image eligibility
  before bridge/ensure_current/prepare_kernel. Cache/native lifetime keys unchanged.
- Header/DEF/profile/checker/loader: exact22 after native ABI proof. Preserve14
  legacy signature subset and21 kernel subset checks while actual DLL has22 exports.
- New C ABI/native smoke/evidence files stay separate from existing41 recipes except
  explicit ABI export-count compatibility updates and source-input binding.

## 7. Verification and acceptance

CPU tests cover structural-only vs executable validation, empty/CUBIN-only images,
alias charging,32/33 dependencies,16MiB/64MiB boundaries, rollback/fault injection,
wrapper-pointer masquerading and copied-buffer lifetime. Variable tests cover
budgets, duplicate/conflict cases, copied names, invalid flags/sizes, first-error
persistence, post-End/retired precedence and concurrent retire/prepare barriers.
Fake Driver asserts zero calls for non-executable registrations and intact ordinary
version1 execution/retirement/context isolation.

Native ABI checks prove RegisterVar declaration, flags and size_t width with the
actual22-export Rust DLL; valid metadata then launching its associated kernel gives801
without a Driver, as do generic version2 functions. Missing/forwarded Driver controls
and all prior Runtime behavior remain required. A local old21-DLL fixture cannot be
silently regenerated as22; its provenance/subset expectation must stay explicit.

New required IDs: `producer.default_device_runtime`, `arc.runtime_default_abi`,
`arc.runtime_default`. Keep the previous41 IDs. Count is established by runner
configuration at execution, not predicted as passes. Separate qualified-host status;
current unsupported host remains diagnostic, release_claim=false.

Positive path: compile the exact existing kernel_oracle.cu/module_a.cu/module_b.cu
bytes with shared cudart and default device-runtime linkage; preserve EXE/fatbin
bytes; use same CT Runtime/Driver on Arc; independently verify17 outputs,4 guards,
both21-element input arrays, single/repeat/ordinary/two-context/parallel/multi-module.
B's expected801 results in its boundaries mode are not blindly reused for C.

Negative path: a CT-owned CU defines and actually reads a volatile device global
from its kernel; fresh compiler imports/registration and preserved PTX must prove
it is not optimized away. Registration itself succeeds as metadata, main is entered,
and cudaLaunchKernel returns801 before native dispatch; explicit sync/free still work.
A host-only report of801 is insufficient: a supplementary typed manual registration
with a forwarding/counting Driver proves no context/load/launch calls on that path.
A variable attached to an otherwise supported user kernel must also block that
registration; a different no-variable token remains usable. Retain no-op launch
numeric control and stale/tampered artifact rejection. No child exit code alone can
establish success. Fresh seeds and hashes are independently replayed.

Record actual candidate/fingerprint/clean identity and independently reconstruct the
complete local bundle. Publish CT-owned sources/design/results only; no vendor assets,
raw observations, machine paths or personal input. Update existing draft PR only after
privacy and user-file hash checks; no merge/release.

## 8. Deferred capabilities

Full global/constant storage, symbol-address/copy APIs, device function resolution,
PTX/cubin cross-module linking, dynamic parallelism, CUDA static runtime imports,
other compiler versions, AMD/NVIDIA execution and supported-host qualification remain
separate work. C is a bounded convenience/compatibility step, not full device-runtime
implementation.

## 9. Builder check and author decisions

Independent read-only builder check on2026-10-23 found no important unanswered
planning question. The conservative module-level launch rule, flat dependency
list, bounds, variable ABI subset and existing41 preservation are explicit author
choices within the previously requested default-link stage, not separately
user-approved implementation details. Self-review moved Result-returning lease
eligibility into the image-ownership task so version2 can never enter the native
path in an intermediate committed task. Fresh producer/ABI/native outcomes may
require revisiting the design; no implementation or passing C result is inferred.
