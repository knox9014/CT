# Bounded Runtime events

The Runtime event subset provides `cudaEventCreate`, `cudaEventRecord`, `cudaEventSynchronize`,
`cudaEventDestroy`, and `cudaEventElapsedTime`. This is a Windows x64 diagnostic
contract over the synchronous Intel Driver backend, not complete CUDA support.

Events have opaque, nonreusing tokens with128 live and4096 lifetime entries per
process. Each owns one native Driver event and one current context. Creation
fences pending work before allocating; optional Driver event5 symbols must all
resolve inside the already owned/pinned Driver. Missing or foreign targets
return35 without disabling mandatory core operations.

Record accepts default or CT-owned streams. It captures a new completion
instance, selects the captured context on the worker, records the native event,
and synchronizes it. The latest instance is published only after accepted queue
submission. Failed acceptance preserves the previous instance. Completion may
happen before publication. No caller stack is borrowed by queued work.

Synchronize snapshots one latest instance and releases all registry/context
locks before waiting. Re-recording cannot extend an older snapshot's wait.
A never-recorded event synchronizes immediately; elapsed on it returns400.
Elapsed checks both latest instances without draining the queue and returns600
while pending. Context locking excludes new record publication during the native
elapsed query; two event locks have stable token order. The same event locks only
once. Output storage is preserved on errors. Error600 has `cudaErrorNotReady`
name; event Driver errors are mapped exactly once, preserving400/600.

Destroy queues native cleanup and immediately closes the logical token after
successful acceptance. Existing snapshot waiters retain their completion state.
A failed acceptance leaves the token usable. Cleanup jobs execute despite a
prior sticky context error; native cleanup failures enter the first-error
context ledger (an earlier error may take precedence) and are never retried. No native cleanup runs
in a Rust destructor.

Unknown/null/closed/foreign-context events return400 (a null required output
returns1). Earlier initialization/queue failures may take precedence over
ownership validation. Completed event errors propagate through synchronize/elapsed.
Normal completion, skipped work, panic and abandoned jobs publish completion.
Publication precedes waking context barriers, so a completed device sync cannot
leave an already completed event reporting pending.

Timing uses native GPU counter differences. Host dispatch and idle gaps may be
included; these are not calibrated kernel-only timings. Native Driver calls do
not synchronize pending Runtime work. No native queue concurrency, overlap,
PTDS, event Query/CreateWithFlags, interprocess event or general framework claim
is made. See [GPU event implementation plan](../superpowers/plans/2026-10-26-gpu-events.md).
