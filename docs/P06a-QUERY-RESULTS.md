# P06a allocation range and pointer metadata slice

Verified 2026-10-21, Windows x64 / Intel Arc B390.
Clean native-tested candidate: `39f97521e9e6c35990754e904555655d09a5c6b2`.
Execution-scope SHA-256:
`883c091ec38f7e056ca4e3e78f92e84f36050776fd1fa91f135e5437eb6e3587`.
Documentation-only heads do not replace this native-tested identity.

## Implemented contract

`cuMemGetAddressRange_v2` returns the containing live allocation's base and byte
size in the current context. Both outputs are independently optional, including
both null; input/context validation still runs. Unowned addresses return500.

`cuPointerGetAttribute` searches all live CT allocation registries independently
of caller TLS for four attributes: IS_MANAGED=8 (unsigned int0), DEVICE_ORDINAL=9
(int), RANGE_START_ADDR=11 (CUdeviceptr), and RANGE_SIZE=12 (size_t). Multiple
owners matching the same numeric address return801; a uniquely matching poisoned
owner returns999. Unowned addresses return1. Every error preserves output bytes.
Queries submit no native commands, edit no TLS and grant no cross-context access.

Known but unsupported attributes1..20 return801; unknown values return1. In
particular CONTEXT/MEMORY_TYPE require UVA in the official contract and are
deferred. No full unified-addressing support is advertised to bypass that gap.
Exports total38, with verified3020/4000 lookup floors. See the precise
[Driver contract](compatibility/driver-api.md) and
[lookup table](compatibility/driver-entrypoints.md).

## Validation

| Gate | Observed result |
| --- | --- |
| Clean required combined cases | 32/32 passed; release_claim=false |
| Rust | 104 normal;106 including prepared cases |
| Python | 62 passed |
| Official CUDA header ABI | 38 signatures, pointer attribute constants and official-PFN calls passed |
| New unchanged native consumer | 64 scalar metadata queries,24 range queries,4,372 preserved bytes |
| Existing Arc, independent consumers and memory slice | All required cases passed |
| Compiler and actual SPIR-V controls | All required cases passed |
| Independent bundle audit | Clean source/config/environment/catalog/tool/input identities matched |

The CT-owned native consumer uses only official CUDA headers. Four allocation
sizes exercise base/interior/final-byte/end/free lookup, optional output
combinations, typed output sentinels, known/unknown/unsupported attributes,
cross-context metadata, no current context, primary reset invalidation, lookup
floors and byte-for-byte memory preservation. Its bytes remain unchanged in the
application-local driver bundle. No original third-party CUDA app is claimed.

RED evidence: the new core lookup test could not compile before the method
existed, and the official-header native consumer failed at missing query exports.
A preserved local older DLL SHA-256
`c9e7ad948ca25ad3e85ca37d10b5cc767ca267762074b5ac29045e57297eaa32`
was subsequently rejected for that missing-export reason. This is an artifact
negative control, not an independently reconstructed baseline source build.

CPU tests cover adjacent allocations, gaps, removal, duplicate ownership and
poisoned owners. Actual hardware failure/duplicate virtual address reproduction
is not established by those synthetic registry checks. Independent read-only
contract and implementation review reported no material findings in inspected
code/tests/ABI paths; final results documentation was checked separately by the
implementer. Publication/identity checks passed; all11 original user files retain
saved hashes. Vendor headers, generated binaries and raw reports stay ignored.
Hosted CPU/validator CI is separately tracked on the stacked draft PR.

## Boundaries and next work

Address-range current-context and pointer-query no-current/stale-TLS policies,
unknown-address errors and failure-output preservation are bounded CT rules;
exact NVIDIA parity is unverified. Numeric addresses may be reused after free,
or begin a different adjacent allocation. No generation-safe pointer identity,
host/mapped/managed allocation, peer/UVA, plural attribute query, virtual-memory
reservation or native resource deallocation proof is inferred.

Together with the [D2D/typed-fill slice](P06a-MEMORY-RESULTS.md), this supplies
bounded metadata for the first synchronous Runtime path. P06a still does not
cover every pointer attribute. The next input is a precise P09a dynamic Runtime
initialization/registration profile and its missing dependencies. P05 nondefault
scheduling, full Runtime/framework/library support and AMD/NVIDIA execution
remain unverified. This is not a universal compatibility or release claim.
