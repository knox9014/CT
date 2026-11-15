# R2i CUDART-only diagnostic table exposure

**Goal:** Observe the next actual Runtime request after the reviewed CUDART table pointer is supplied. No hooks table/buffer exposure or successful private operation. Production CT and Driver version remain unchanged.

**Design:** Separate ExportRejectObserver subclass. Preserve its v2-only labelled resolver presentation and existing missing-export/rejection controls. Reject earlyf8 query801, present the R2h test-only CUDART pointer only for post-init6bd query, then separately label/reject known-nexta094 query801. Require this exact order, actual init0 and Runtime801/count−1. Null args return1 without UUID reads. Unknown order/ID/precondition/failure clears output and invalidates the child.

Authenticate the fresh standalone fixture capture and copied DLL. Validate table pointer/image bounds,104-byte metadata, zero holes and all callable targets inside that exact loaded image. No typed function is invoked by the observer. Check the fixture's one-atomic mask/stop state before, during and after the Runtime call and teardown. Nonzero mask blocks further wrapped callbacks and invalidates the child. All fixture callbacks themselves deny/no-forward; the latch is not a native sandbox.

Keep the fixture loaded through all Runtime teardown and callback lifetimes; verify Runtime unload first, then fixture unload, with no pointer/callback use after unload. Never widen the base rejection identifier set globally. This is explicitly a diagnostic table-pointer presentation, not a product cuGetExportTable implementation or claimed table service.

- [x] Write failing tests for finite query order, null/output behavior, unknown IDs, latch blocking, pointer layout/targets and exact result metadata.
- [x] Implement separate exposure observer/worker/checker and local runner. Keep default workers/production unchanged.
- [x] Run fresh typed fixture Rust3/C++47 controls, original bootstrap/rejection controls, both fixed exposure samples, and final unchanged faithful/nominal controls. Stop before advancing on any guard, nonzero private bit, fault, drift or unreviewed status.
- [x] Independently review completed code, bind source/artifacts/observations, run saved recheck, full CPU regression and privacy/protected-file/index checks. Record next request without inventing its semantics.

## Outcome

Both fixed samples accepted the labelled CUDART pointer and reached the expected a094 hooks query, rejected801. Private mask remained0 before/prefix/afterRuntime; unload and controls passed. Fresh fixtureRust3/C++47,17bootstrapchildren,7focusedtests, independent review and cleanCPU11/11 passed. See `docs/R2I-CUDART-TABLE-EXPOSURE-RESULTS.md`. No actual private operation/application support was added.
