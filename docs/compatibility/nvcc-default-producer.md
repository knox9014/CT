# Default device-runtime producer recipe

This extends the authenticated nvcc12.0.76 A producer through a separately audited
manifest. Keep shared cudart and non-RDC PTX8.0/sm52; omit the cudadevrt=none flag.
All NVIDIA binaries, original headers/libraries, host tools and installed host
snapshot remain bound to the A manifest. Environment normalization and explicit
compiler selection are reused; unsupported-host evidence stays diagnostic.

Run `python scripts/prepare_nvcc_default.py prepare`, then `replay`. Artifacts stay
under the ignored configured producer cache. The CT-owned observer intentionally
fails allocation and exits11, recording only constructor structure, raw dependencies
and owned metadata. It is not Runtime or GPU proof. Actual original/CT/Rust callback
ABI is a separate native gate. Observer ABI types are independent CT declarations;
no vendor header is edited or used as a stub implementation.

The pinned producer emits v1 user code and a v2 registration with an empty own
container and one machine-code-only raw dependency. Observe bounded counts and
metadata, bind all artifact/source/command hashes and independently check raw extents.
The dlink output prefix follows the executable name, default_dlink. No private
symbol-name decision exists in the product. Native default-link execution and
used-global rejection require their separate Arc gates.
