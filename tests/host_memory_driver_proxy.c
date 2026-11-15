/* Optional host extension controls; all core operations use genuine CT. */
#include "p04a_noop_driver.c"
CUresult CT_CUDA_API cuMemHostAlloc(void **out,size_t size,unsigned int flags) {
    PFN_cuMemHostAlloc f=(PFN_cuMemHostAlloc)resolve("cuMemHostAlloc");
    return f?f(out,size,flags):999;
}
CUresult CT_CUDA_API cuMemFreeHost(void *pointer) {
    PFN_cuMemFreeHost f=(PFN_cuMemFreeHost)resolve("cuMemFreeHost");
    return f?f(pointer):999;
}
