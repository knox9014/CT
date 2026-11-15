# R2m: typed callback uses the public provider's global state

The new Rust-visible `cudart_primary_context` function has the reviewed `unsafe extern "system" fn(*mut *mut c_void, i32) -> i32` shape and delegates to the same global Runtime used by CT's public CUDA functions. Null validation and valid-output clearing happen before invoke, including before a possible lock failure. It has no no_mangle attribute and no CUDA resolver/header/profile entry.

In a fresh-process native test on Intel(R) Arc(TM) B390 GPU, the typed callback returned3 before initialization with null output, and1 for null storage. After cuInit it returned an inactive owned handle, reused it on lookup and shared the identical handle with public retain. Active lookup added no extra usage: one public release retired it. A real ordinary current context was preserved across calls; reservation reset and pending-usage801 were checked. Final current state and CT-owned/quarantined context maps were empty. This tests callback ABI/global state, not official CUDA Runtime execution or GPU-driver-wide leak behavior.

Actual production DLL inspection found exactly the46 declared exports, unchanged. Rust visibility did not create a new C DLL entry. A separate compile-only diagnostic link probe also confirmed that the rlib's public CUDA exports and callback can coexist in one linked provider; that probe was not loaded and is not native Runtime evidence.

Tests were written first and failed on missing callback. Related CPU tests then passed15 with2 native cases excluded; an independent reviewer repeated that check and reviewed the native test before hardware execution. The required clean CPU lane passed11/11: Python329, Rust215 with6 ignored tests, Runtime129, formatting, Clippy, profiles/registry and publication checks. The new global callback native case passed separately1/1; other ignored cases were not implicitly executed by this CPU run.

Source fingerprint: `eb1ff75c53725c1e029977f55ec3072f0dc845dd9df4536a1d68dc00ce2b9400`. Private checkpoint commit: `6dac304c37afae8963f085f08af78268784b0e92`; tree: `9915fa803c74df0700a095ea558240b7952ab7cb`. Ignored local capture records native command/log/compiler identity and production DLL/export hashes. Final local verification separately checks source, privacy and protected files/HEAD/index. No staging, root commit, upload or managed-worktree edits were performed.

Reproduce the new native case alone in a fresh process:

```text
cargo test --locked -p ct-cuda --lib primary_callback_tests::native_global_primary_callback_matches_public_lifecycle -- --ignored --exact --nocapture --test-threads=1
```

Next build a diagnostic provider that links both public functions and the private table callback into this same global state. A provider linked separately from a loaded CT DLL would have a separate Runtime and must not be mixed with it. Keep production export behavior unchanged; gate the first new Runtime prefix at the next public call and clean the inactive reservation after Runtime teardown. No application support is claimed by this stage.
