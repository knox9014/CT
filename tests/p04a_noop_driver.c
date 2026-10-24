/* Preserve the full global path before suppressing launch for numerical control. */
#include "p09a_noop_driver.c"
CUresult CT_CUDA_API cuModuleGetGlobal_v2(CUdeviceptr *p,size_t *n,CUmodule m,const char *name) {
 PFN_cuModuleGetGlobal_v2 f=(PFN_cuModuleGetGlobal_v2)resolve("cuModuleGetGlobal_v2");return f?f(p,n,m,name):999;
}
