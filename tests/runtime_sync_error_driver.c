/* Synthetic synchronization error, with all other core operations forwarded. */
#define cuCtxSynchronize ct_hidden_synchronize
#include "p09a_noop_driver.c"
#undef cuCtxSynchronize
CUresult CT_CUDA_API cuCtxSynchronize(void) { return 709; }
