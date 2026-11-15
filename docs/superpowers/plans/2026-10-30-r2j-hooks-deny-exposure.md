# R2j hooks-table deny exposure and first private context boundary

**Goal:** Expose only the already validated typed deny layouts and observe the first private callback. No real buffers, private context service, module loading or product changes.

Independent static review confirmed that Runtime22d60 calls15cb0 before the hooks getters. It invokes actual cuDeviceGetCount, cuDeviceGet, then CUDART slot2. A denied slot2 sets fixture bit2; Runtime15cb0 resets its internal count and returns its initialization value3, not801. The finite expected result is Runtime3/count−1 with actual Driver count0/value1 and DeviceGet0/value0 for ordinal0. Do not broaden this expected branch after an unexpected run.

**Architecture:** Separate subclass/worker/checker; reuse authenticated R2h fixture and R2i pointer/lifetime gates. Validate the56-byte hooks layout before returning its address only for the exact third query. All fixture callbacks still deny. Expected private state transitions0→mask2/stopped1; no other bits. The expected hit is a distinct diagnostic outcome; any further wrapped prefix call is blocked and invalidates completion. Direct version/context controls after Runtime teardown remain intentional controls outside the observed prefix.

- [x] Add failing tests for hooks bounds/holes, exact expected latch versus unexpected bits, typed DeviceGet observation and finite status/order gates.
- [x] Implement separate hooks-deny observer/worker/checker/runner. Preserve prior workers and base rejection scope.
- [x] Independently review before native execution. Run fresh fixture Rust3/C++47, prior R2i17 bootstrap children, then two hooks exposures and final two controls, totaling21 bootstrap children. Keep masks0 in prior controls and exactly2 only in the new expected-denial arms. No hook getters may run.
- [x] Review saved evidence and run clean CPU regression, source/artifact recheck, privacy/protected-file/HEAD/index verification. Record missing private context semantics without inventing success.

The latch is not a complete native-call sandbox. Keep fixture/callback lifetimes through Runtime restore/unload, capture final state before fixture free, and never call/read fixture after unload. Public module/launch guards and typed private denials remain active. No staging, root commit, upload, install or accepted-worktree edit.
