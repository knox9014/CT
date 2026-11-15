# Runtime device attribute implementation

Add cudaDeviceGetAttribute as Runtime27, forwarding only existing Driver attributes 1..7 and 20. Keep Driver39 and mandatory bootstrap15/kernel5 unchanged. Unsupported attributes, including CUDA compute capability, return 801 without loading a Driver. Null output returns 1, then negative ordinal 101, then unsupported attribute 801. Preserve output on every error.

1. Add failing profile and injectable Runtime tests for all supported attributes, handle translation, error domains, preflight, TLS and no context operations.
2. Add independent lazy owned-module resolution for cuDeviceGetAttribute; preserve Runtime loader error35 directly and map raw Driver errors once.
3. Extend the current header, import library and profile to27; update active native count/evidence gates while retaining historical results.
4. Compile and run official-header ABI/native attribute checks, plus missing/forwarded provider controls. Run Rust/Python regression, existing CUDA vectorAdd and static matrixMul triage as practical.
5. Obtain independent source review, check privacy/baseline hashes and document verified scope. No matrixMul execution or general CUDA capability claim.
