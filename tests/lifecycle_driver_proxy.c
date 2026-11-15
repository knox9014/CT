/* Controls only. Preserve stale-function validation when arguments are absent. */
#define cuLaunchKernel ct_passthrough_launch
#define cuModuleUnload ct_passthrough_unload
#include "host_memory_driver_proxy.c"
#undef cuLaunchKernel
#undef cuModuleUnload
CUresult CT_CUDA_API cuLaunchKernel(CUfunction f,unsigned gx,unsigned gy,unsigned gz,unsigned bx,unsigned by,unsigned bz,unsigned shared,CUstream stream,void **arguments,void **extra) {
#ifdef LIFETIME_NOOP_LAUNCH
    if(arguments)return 0;
#endif
    return ct_passthrough_launch(f,gx,gy,gz,bx,by,bz,shared,stream,arguments,extra);
}
CUresult CT_CUDA_API cuModuleUnload(CUmodule module) {
#ifdef LIFETIME_NOOP_UNLOAD
    (void)module;return 0;
#else
    return ct_passthrough_unload(module);
#endif
}
