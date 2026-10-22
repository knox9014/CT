# P09a2: genuine nvcc Runtime kernel connection

Verified 2026-10-22 on Windows x64 / Intel Arc B390.
Native-tested code candidate: `bf36cff10a7b66221d339bf49de9f61c5209e9b6`.
Execution-scope SHA-256:
`e24e938274a38bdbc3714e2ea322be98fb75898febe8e2fc321689a8073ecdd8`.
Documentation-only commits do not replace this native-tested identity.
Independent whole-B review identified one terminal callback-state defect.
The fixed candidate above passed the complete clean required41 rerun.
Independent read-only fixed-bundle reconstruction returned `errors=[]`,
verified the same code/fingerprint and41 pass statuses, with no skipped or
unavailable required cases. Publication scans passed and all11 original user-file
hashes are unchanged.

## Implemented and tested

Genuine nvcc12 compiler-generated constructors and launch stubs now reach the
standalone Rust Runtime21 DLL, the same pinned CT Driver and Intel Arc.
Executable and embedded GPU-code bytes are preserved. No system driver is replaced.
The tested producer uses `--cudart=shared --cudadevrt=none`, non-RDC PTX8.0/sm52.

The decoder accepts a distinct bounded nvcc container profile, including compressed
and plain PTX, while retaining existing nvFatbin validation. Constructor callbacks
own bounded CPU registration data. Kernel launch creates context-specific native
modules lazily; launch leases, retirement and explicit cleanup protect their lifetimes.
The Runtime links only the pure decoder, with no static CT Driver/backend dependency.

The clean required combined run passed **41/41** gates, with no errors, at the
candidate and fingerprint above. All previous38 gates remain; the three additions are
`producer.nvcc_fatbin`, `arc.runtime_kernel_abi` and `arc.runtime_kernel`.
The report records `clean=true` and `release_claim=false`. Local bundles and raw logs
remain ignored and are not published.

Native ABI probes check original vendor declarations, independent CT declarations,
exactly21 DLL exports and actual typed calls. Missing or forwarded kernel-provider
symbols return35 while the existing memory API remains usable. The prior14-API
memory gates remain separate checks.

The native oracle covers seven genuine-nvcc scenarios: single/repeated launches,
ordinary current context, two contexts, parallel first use, same-named kernels in
two modules and error boundaries. Each checks17 outputs, four guards and both
input arrays independently. Supplemental actual-Arc registration retirement checks
reject later launches and drain safely. A no-op launch provider returns success but
is rejected by the numeric oracle. Capture independently reruns fresh seeds and
binds source, producer, executable, import, fatbin and DLL hashes.

## Evidence limits and next step

This is **diagnostic host evidence**. NVIDIA component archives and original STL
bytes are authenticated; the installed newer MSVC/SDK is a complete local hash
snapshot using the explicit unsupported-host diagnostic path. No reviewed supported
host pin exists yet, so qualified-host success remains unavailable.

Default nvcc device-runtime linking, Runtime22, version2 prelinked inputs and
`__cudaRegisterVar` remain P09a2-C. Frameworks, broad CUDA compatibility, full
globals/device linking, release readiness, AMD and NVIDIA execution remain unverified.
The next stage is a separately bounded C design followed by the default-build
numeric/guard/input oracle and a used-unsupported-variable negative fixture.

## Implementation rulings

- Preserve the existing feature checkout and use an attached clean worktree for
  acceptance. Exact staging and11 original-file hash checks protect user changes.
  An ignored PowerShell ledger replaces unavailable Bash helpers.
- Authenticate vendor archives separately from the local host-tool snapshot.
  Keep the supported-host qualification registry empty until independently reviewed.
- Compare compressed/plain embedded payloads; standalone PTX comments differ.
  Bound declared decoded size before allocation. Other allocator-abort paths
  remain outside the recoverable decoder-allocation contract.
- Cache missing functions per symbol; retain bounded failed-load ownership records.
  Explicit synchronize may drain eligible retired modules in the current context,
  allowing budgets to recover even when no further launch is possible.
- Use the official opaque stream type. Split official registration and CUDA launch
  type probes into translation units; empty-fatbin type-probe link shims provide
  no execution evidence. Separate actual Rust DLL probes exercise all seven APIs.
- Copy CT-owned CUDA source byte-identically into a local relative-output build
  directory to avoid host path encoding issues; vendor headers and executables
  are unchanged. Build the foreign control provider before linking its forwarder.
- Accept module-local `.entry` needed by genuine static kernels, preserving
  uniqueness and external/weak/device-link restrictions.
- Retain bounded failed-callback host associations so launch reports the scoped
  error instead of an unrelated missing-function error. Exhausted mapping budgets
  still fail closed. No vendor-name exception or unimplemented successful callback
  was added.

The independent A review found two important issues (compression-mode binding and
inherited compiler flags) plus an allocation-order issue promoted from minor.
All were reproduced and fixed with regression checks. No A minor finding was deferred.

The independent B review found that a later malformed callback could overwrite
an existing failed-registration code, and retired/unknown tokens could report
payload errors instead of98. This P2 was treated as important because terminal
error persistence is an explicit contract. Two registry/export regressions failed
before the fix; both now pass, along with all42 Runtime tests and clippy.
Token state is validated before reading callback payloads and checked again under
the registry lock. No minor finding was deferred. The first preferred-model
review attempt hit its usage limit; its unfinished output was excluded. An
available independent reviewer completed the code review and baseline bundle audit. The actual fixed Runtime DLL also passed five
CPU-only terminal-state regression assertions outside the Rust test process.
