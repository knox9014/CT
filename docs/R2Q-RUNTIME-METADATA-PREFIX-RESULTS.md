# R2q: actual Runtime name and total-memory prefix

The pinned official CUDA Runtime 12.9.79 queried CT's real Intel device name and `cuDeviceTotalMem_v2` after one guarded native primary-context call. Both diagnostic version samples then stopped at the actual default-strict `cuDeviceGetAttribute(75)` refusal: Driver 801/output 0, Runtime 3/count -1. No attribute 76, application execution, shipping CUDA version or general compatibility is authorized by this result.

The observed name was `Intel(R) Arc(TM) B390 GPU`, and the reported total was 17578409984 bytes. Both matched separate direct/public controls. This is a driver-advertised total, not free memory, dedicated VRAM, an allocation budget or an atomic snapshot. The exact prefix was context, name (256-byte bounded buffer), size_t total, then attribute 75. Actual device calls were forwarded; only the already-labelled private Runtime bootstrap experiment supplied its diagnostic table/version surface.

The fresh capture contains 20 children: the existing 8 production baselines, 8 shared-provider context-bridge children, and 2 metadata samples plus 2 final controls. The C++ private deny-table consumer retained 47 checks. Native context counters remained calls/result/non-null 1/0/1, private denial counters stayed zero, Runtime unload and patch restoration passed, and primary reset left the public primary inactive and current context null. Foreign Windows loader lookups remain outside the CUDA forwarding gate; they do not authorize any extra CUDA call after refusal.

The immutable clean CPU lane passed 11/11: Python 339 tests, Rust 223 passed with 7 ignored, Runtime 129 passed, formatting, Clippy, profiles, registry and publication. The ignored Rust tests were not GPU passes. The new metadata tests cover ordering, scalar types, actual control values, strict policy, refusal/latch and sample identity. No production Rust behavior was added in this phase.

Source fingerprint: `4a333991e453077b5d280eb57f2100df429618f0b27b62ceaff920de5ab18d6b`.
Private source checkpoint: `2d17e36a959b651aa1eb9248738e7c9a0ce79dff`.
Accepted capture: `96c81a28f8c94b328f04b9a8620eedf5`.
Metadata capture SHA256: `1b9e89916adfd5375c5ccb3999cbe432ef39576b0ad810cdbc79927658fb69b9`.

On 2026-11-02 the saved capture consistency check and immutable source-candidate verification passed again before implementation resumed. This was a saved audit, not another native GPU run. Raw paths, binaries, SDK contents and logs remain ignored and were included in the private encrypted Drive backup; keys remain only on the notebook. HEAD/index and the 11 protected files remain unchanged.

Next observe the existing explicit `ct-sm52-subset-v1` software-target policy in separately labelled fresh children, then query the actual next unsupported attribute. Default-strict behavior and public Driver version refusal must remain intact; software-target major/minor values are not NVIDIA hardware or conformance claims.
