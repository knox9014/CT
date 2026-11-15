# CT device capability policy

CT exposes real limits bounded by its implemented execution profile. Physical
device identity remains Intel. A PTX target accepted by the translator is a
source-format/feature-profile decision, not a declaration of complete NVIDIA
hardware-architecture support.

## Current device contract

- Driver/Runtime attributes1..7: real group/grid limits under existing bounds.
- Attribute8: min(native Level Zero maxSharedLocalMemory,16384), in bytes. This
  is CT's bounded static-shared capacity; dynamic launch shared bytes remain
  unsupported.
- Attribute20: shared/default compute mode,0.
- Attributes75/76: strict801 by default. Explicit `CT_VIRTUAL_TARGET=ct-sm52-subset-v1`
  enables virtual selection target5.2; physical Intel identity is unchanged.
- NVIDIA SM count/clock ranking: unsupported; Intel EU/clock metrics are not
  substituted for NVIDIA SM performance estimates.

The single translator bound is ct_ptx::MAX_STATIC_SHARED_BYTES. Parsing and public
IR revalidation use that value. Each compiled entry retains the sum of declared
shared objects rounded individually to their declared alignment. Before native
module creation, the Driver checks every selected entry against the owning
device's bounded capacity. Independent entries do not consume storage at the same
time and are not summed. A rejected requirement never invokes the native creator;
an accepted requirement preserves its ordinary native error. The native compiler
may still reject actual resources within a conservative declaration budget.

Fatbin selection validates every candidate's translation, metadata, duplicate
profile, global identity and complete entry ABI. It then chooses the highest
ranked candidate whose every entry fits the owning device's bounded capacity.
Ranking remains PTX8.0/sm52 above PTX7.0/sm50, independent of record order. A valid
nonfitting alternative does not prevent selecting a fitting alternative; an
invalid/unsupported alternative still rejects the entire input. No fitting
candidate returns801. This is capacity-based selection before native compilation;
ordinary native compilation/resource errors propagate without retrying variants.

## Virtual architecture decision

Research on2026-10-27: [ZLUDA's device implementation](https://github.com/vosen/ZLUDA/blob/master/zluda/src/impl/device.rs)
returns its global compatibility-layer compute capability for major/minor
queries. [chipStar's documentation](https://github.com/CHIP-SPV/chipStar)
describes CUDA/HIP execution via SPIR-V and separately lists unsupported features.
These are different compatibility designs and do not establish that CT can adopt
either project's advertised architecture values.

Before CT advertises a virtual architecture, define its selection meaning, the
supported feature matrix, behavior of late-registered/unsupported kernels, kernel
selection across fatbins, and application-visible limitations. Validate an actual
application without test metadata injection and independently check its numerical
outputs. An opt-in setting that merely moves injected5.2 into the product is not
that contract.

## Implemented experimental target

Driver is the sole authority. The first valid cuInit(0) attempt snapshots
CT_VIRTUAL_TARGET before native initialization. Unset or strict selects strict;
ct-sm52-subset-v1 selects the bounded virtual target. Empty, unknown and non-Unicode
values give persistent init error1. Native init failure does not reopen the policy;
nonzero flags do not consume its latch. Environment mutation after initialization
does not change the selected mode.

Runtime delegates75/76 to the owned Driver and never reads configuration. This
deliberately replaces the earlier Driver-free CC rejection: with an owned strict
Driver the result remains801, but missing/foreign binding gives35 and a positive
invalid ordinal gives101. Null1/negative101/other unsupported801 preflight stays
Driver-free. Query outputs/TLS/context contracts are preserved.

Accepted PTX pairs and complete supported-operation/API/resource references are
listed in [the machine-readable contract](compatibility/virtual-target-v1.json).
Existing translation/selection checks remain authoritative for unsupported and
late-registered code. No full NVIDIA architecture conformance is implied, and
automatic NVIDIA-style performance ranking stays unsupported. First application
scope is explicit device selection.

The older [metadata-injected diagnostic](MATRIX-RUNTIME-ISOLATION-RESULTS.md)
remains a historical test. The new product qualification uses CT Driver/Runtime
directly; an observational Driver can capture numerical data without overriding
metadata. Strict, experimental and metadata-injected results must stay distinct.
