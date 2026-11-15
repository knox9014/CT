# Uniform block barrier first slice

User delegated implementation choices and asked to continue the approved shared
memory/synchronization direction. First implement the synchronization foundation:
canonical decimal `bar.sync 0;`, with no count, predicate, alternate IDs, warp,
cluster, arrive/reduction or memory-space additions. Static shared storage and
matrixMul remain later work. Do not treat accepting a name as execution support.

IR adds BlockBarrier. A kernel containing it must have exactly one block ending
in Return, so every launched invocation executes the same barrier sequence.
Reject any CFG (even an apparently uniform jump/loop) before GPU submission.
Existing kernels without barriers retain their CFG support. Bounds remain4096
instructions/kernel. Alignment and def/use treat barrier as no register change.

Emit OpControlBarrier224 with U32 constant IDs for execution Workgroup2, memory
Workgroup2, semantics SequentiallyConsistent16 | WorkgroupMemory256 |
CrossWorkgroupMemory512 =784 (0x310). This covers CTA global+future shared ordering
and fits OpenCL1.2 validator rules; the stronger memory order is deliberate.
No memory-only substitute or CPU synchronization can satisfy the barrier.

Tests first: parse acceptance/order; reject nonzero/dynamic/counted/predicated/
branch/jump/loop cases; preserve ordinary CFG; inspect SPIR-V instruction operands
and const values; pinned spirv-val --target-env opencl1.2. Validate genuine nvcc
__syncthreads PTX and original fatbin token correspondence. A race-free staged
publish/exchange kernel uses separate scratch/output regions and barriers between
writes and peer reads, multiple blocks and more than32threads/block. Compare all
output data independently, guard bounds, test renamed entries and real CUDA ABI.
No-op launch/copy controls detect omitted execution. Do not claim that removing
barriers must numerically fail deterministically on every GPU; static exact
opcode/semantics and native validation supply that evidence. Never run divergent
barrier code or deliberately induce GPU hangs.

Use independent read-only review. Finish compatibility docs before source freeze;
then native/regression captures, original vectorAdd and offline matrix diagnosis,
privacy scan, preserve user11 baseline files, ignored local artifacts only.
Driver46 / Runtime40 unchanged. No staging/upload or AMD/NVIDIA/benchmark claim.

References:
https://registry.khronos.org/OpenCL/specs/unified/html/OpenCL_Env.html
https://registry.khronos.org/SPIR-V/specs/unified1/SPIRV.html
https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html
Pinned SPIRV-Headers/Tools revisions remain the existing toolchain lock.


Ruling after actual validator experiment: the pinned validator accepts a module
whose execution scope is changed to Invocation. This is not evidence of correct
CTA semantics. Exact static mapping checks must reject that semantic mutation;
use an undefined-ID mutation for the validator liveness/rejection control. Neither
mutated module is ever submitted to GPU. Positive validation plus native results
and exact lowering checks remain separate acceptance evidence.

Previously unsupported-instruction fixtures used bar.sync0. They now use still
unsupported bar.sync1, preserving unselected-candidate/module/CLI rejection tests.

## Execution ledger

Completed the bounded single-block implementation, rejection tests, SPIR-V exact
operand checks and genuine nvcc/Intel native capture. Two seeds each verify704
output words across64x3 and128x4 launches, plus guards/input/scratch checks.
Official validator positive and undefined-ID negative controls pass; the semantic
scope mutation is rejected separately without GPU submission. No-op launch/copy
controls detect omitted work. Independent review artifact-hash hardening was
applied before freezing source.

Python197, Runtime Rust129, workspace tests, clippy and format checks pass.
Fresh original vectorAdd capture/replay pass; original matrixMul remains blocked
at shared line32 with zero missing Runtime imports and no application/GPU run.
Source-bound evidence and limitations: [results](../../UNIFORM-BLOCK-BARRIER-RESULTS.md).
Next slice is static shared storage/addressing/alignment; do not broaden barrier
CFG support implicitly or claim matrixMul execution from this milestone.
