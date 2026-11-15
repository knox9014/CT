# CT verified development checkpoint — 2026-11-15

This checkpoint preserves the accumulated Intel implementation, its synthetic tests,
explicitly labelled diagnostics, compatibility contracts and historical result documents.
It is a development checkpoint, not a release or a claim of general CUDA compatibility.

## Scope

- Bounded PTX memory/alignment, shared memory, uniform barriers/control flow and F32 FMA.
- CT-owned Runtime host allocations, streams, queued submissions, events and profiler import closure.
- Device capacity selection, explicit software-target metadata, primary-context and memory queries.
- Numba-related bounded parser/ABI work and raw Level Zero kernel-resource queries.
- Reproducibility, validation, publication guards and documented diagnostic-only Runtime experiments.
- Existing MIT licensing and bilingual usage documentation.

Experimental providers, private-table probes and the Numba adapter runner remain
explicitly experimental. Their presence does not enable ordinary CuPy/Numba applications.
Generated adapters, SDKs, build products, raw logs and private captures are not committed.

## Fresh checks on this working checkout

The product/test source fingerprint before recording this summary was:

`fcc304dae665e49ce0cf7eb68f349ad9d8f45d61fcd9a861fd82618d07798be0`

- Required CPU lane: 11/11 passed, no report errors.
- Rust workspace: 231 passed, 0 failed, 7 existing ignored tests.
- Separate CT Runtime: 129 passed, 0 failed.
- Python: 394 passed.
- Workspace and Runtime formatting/Clippy, coverage/profile checks and publication scan passed.
- Repository-configured whitespace check passed.
- Fresh Intel Arc B390 native SPIR-V smoke: 16 size/group combinations passed with zero numerical error.
- Fresh translation of `tests/fixtures/kernel_resources.ptx` and backend resource queries passed.
  `no_shared` reported 0 local bytes; `with_shared` reported 4096 local bytes.
  Both had one argument and maximum subgroup size/count 32/32.

The smoke uses prepared SPIR-V and is explicitly not CUDA application qualification.
The two resource queries inspect metadata; they do not prove CUDA register counts,
occupancy, general function attributes or application performance.
Historical matrix, official Runtime and Numba captures were not rerun in full for this checkpoint.

The CPU report records `clean=false` because the changes had not yet been committed.
This is not a fresh clean-checkout or other-machine validation claim.
Machine-local reports remain under ignored `results/local/commit-review-2026-11-15/`.

## Storage and publication

The `.cache` headroom guard refused additional cache reservation because the existing
cache exceeds its configured limit. No historical evidence was deleted or moved and no
budget limit was weakened. Checks reused an existing ignored `target` directory with
more than 100 GiB free on the volume. This does not qualify all build-output locations
under the cache guard.

Staged blobs and the configured noreply Git identity are checked before commit.
This task creates a local commit only; it does not push, merge or change the default branch.

After the checks above, staging found one extra blank line at the end of
`scripts/runtime_virtual_metadata_check.py`. Only that trailing blank line was removed.
The Python AST was verified unchanged and the focused virtual-metadata tests passed.
Final product/test fingerprint after this whitespace-only normalization:

`3e19d1eeb004deefe50a111dea42d820f7441a052300f1bf187367d01562a302`
