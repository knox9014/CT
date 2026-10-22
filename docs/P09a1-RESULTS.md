# P09a1: shared-state synchronous Runtime results

Verified 2026-10-22, Windows x64 / Intel Arc B390.
Clean native-tested candidate: `24ef127a8eaf813e4918c1ec091b5aa359a90166`.
Execution-scope SHA-256:
`0773b846924e27544d0214123d48150a37dd2c0379e802dacf60c59c73cecfbf`.
Documentation-only heads do not replace this native-tested identity.

## Implemented boundary

The standalone Rust `ct-cudart` DLL supplies the bounded14-entry Runtime profile
in [runtime-profile-v1.json](compatibility/runtime-profile-v1.json). An explicit
`ct.py run --ct-dll ... --runtime-dll ... application.exe` bundles it as
`cudart64_12.dll` beside one CT `nvcuda.dll`. The executable and both DLL payloads
are copied byte-for-byte; system drivers are not replaced.

Device selection, synchronization, allocation/free, explicit synchronous copies,
byte fill and Runtime error helpers call the same Driver ABI. The Runtime links
no CT Driver/backend Rust library and owns no duplicate allocation registry.
It preserves ordinary current Driver contexts and caches one process-lifetime
primary retain per device. Selection rollback failure is sticky999; stale cached
contexts fail709 without automatic recovery. Module identity, owned references,
all required exports and module pinning are checked before Driver calls.

The profile deliberately returns801/zero for version queries; the DLL name is
not a full CUDA12 implementation claim. Zero allocation and Default/UVA copies
are unsupported. Valid zero-byte copies/fills and explicit host-to-host copy
avoid Driver initialization. Successful operations preserve prior Runtime TLS
errors; GetLastError clears only the calling thread's error. Driver201 maps to
Runtime49; unexpected codes map to999 instead of being cast between enums.

## Observed verification

| Gate | Observed result |
| --- | --- |
| Clean required combined lane | 38/38 passed; clean=true; release_claim=false |
| Existing Driver/producer/SPIR-V/Arc regressions | All32 prior required gates retained and passed |
| Standalone Runtime Rust | 14 passed; fmt/clippy passed |
| Existing workspace Rust | 104 normal;106 including prepared cases |
| Python | 70 passed |
| Official Runtime ABI | 14 signatures; copy kinds0..4 and12 error values matched |
| Header provenance | Actual MSVC include closure:8 Runtime headers +1 compiler support header |
| Actual native consumer | 9 positive modes;2 deliberately incorrect providers detected |
| Memory interoperation | Primary and ordinary-context modes each checked8,770 output/guard bytes |
| Independent execution | Runner replayed2 ABI probes and all11 native modes with fresh processes/seeds |
| Independent stored-evidence audit | Source/config/tools/environment/report and actual artifact hashes matched |
| Publication/user-file checks | Passed; all11 original user-file hashes preserved |

The CT-owned consumer compiles against authenticated official Runtime headers
and a CT-owned import library. Its PE imports exactly the14 named Runtime
functions. It is not an original third-party distributed CUDA application.
It checks Count/Get without primary activation, eager SetDevice, Runtime/Driver
allocation-copy-fill-free interoperation, ordinary-context preservation, odd
lengths, read-only input preservation and guards. Two threads exercise error
isolation and repeated selection. A separate end-of-process primary-reference
probe releases the external reference, observes active state, then releases the
single expected Runtime reference and observes inactive state before exit.
This destructive probe does not authorize ordinary clients to steal references.

Fresh children cover Driver absence, a wrong-location Driver, missing exports,
stale/reset709 and Driver-free pure helpers. Wrong/missing-export providers are
held loaded and must report an actual zero init-call counter. The two negative
providers forward to a separately named real CT Driver on Arc, but skip H2D or
the target byte-fill operation. Independent byte comparison rejects both with
exit42 and the respective copy/fill oracle mismatch. Controls do not add support
cases. Inputs and output sentinels vary with each execution's seed.

## Failure evidence and review

Initial Runtime error/TLS tests failed against explicit placeholders. Five state
and five memory behavior tests failed before their implementations. Loader tests
failed before the opt-in existed; the runner test failed before the six nested
Runtime gates were added. A faulty fill control initially skipped baseline fill
as well; the audit rejected its wrong failure phase, then the control was narrowed
to the intended target operation.

Independent review found that complete fabricated log/hash manifests could pass
a structure-only audit. The runner now directly re-executes the bound native
programs before granting a required pass, and rechecks native source/payload
identity afterward. A complete synthetic manifest cannot pass execution checking.
Review also exposed a memory test failing during init rather than during memory
operations: an exact operation-call assertion was observed failing, then fault
injection was separated. Mandatory fake-provider counters, production cache-helper
coverage and variable output sentinels were also added. Read-only re-review found
no remaining Important/Critical issue. A separate read-only clean-bundle audit
reported no errors; it did not itself execute GPU work.

## Remaining scope

P09a2 still needs a real pinned nvcc host compiler and observation of its shared
cudart host stubs, fatbin wrapper/registration, host-function mapping and kernel
launch. Cached NVRTC PTX and the nvcc support wheel are not evidence of nvcc host
compilation. Runtime14 memory success does not establish CUDA kernel registration,
original dynamic/static NVIDIA cudart, streams/async, UVA/managed memory, reset
recovery, general PTX, CUDA math libraries, frameworks or distributed applications.
AMD and NVIDIA hardware execution remain unverified.

Raw headers, binaries, include-path logs and run manifests remain ignored local
artifacts. This milestone is a bounded application-connection step toward the
universal CUDA goal, not universal compatibility or a release claim.
