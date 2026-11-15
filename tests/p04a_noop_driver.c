/* Preserve the full global path before suppressing launch for numerical control. */
#include "p09a_noop_driver.c"
CUresult CT_CUDA_API cuModuleGetGlobal_v2(CUdeviceptr *p,size_t *n,CUmodule m,const char *name) {
 PFN_cuModuleGetGlobal_v2 f=(PFN_cuModuleGetGlobal_v2)resolve("cuModuleGetGlobal_v2");return f?f(p,n,m,name):999;
}

CUresult CT_CUDA_API cuEventCreate(CUevent *out,unsigned int flags) {
 PFN_cuEventCreate f=(PFN_cuEventCreate)resolve("cuEventCreate");return f?f(out,flags):999;
}
CUresult CT_CUDA_API cuEventRecord(CUevent event,CUstream stream) {
#ifdef EVENT_NOOP_RECORD
 if(stream)return 801;
 {PFN_cuEventSynchronize f=(PFN_cuEventSynchronize)resolve("cuEventSynchronize");return f?f(event):999;}
#else
 PFN_cuEventRecord f=(PFN_cuEventRecord)resolve("cuEventRecord");return f?f(event,stream):999;
#endif
}
CUresult CT_CUDA_API cuEventSynchronize(CUevent event) {
 PFN_cuEventSynchronize f=(PFN_cuEventSynchronize)resolve("cuEventSynchronize");return f?f(event):999;
}
CUresult CT_CUDA_API cuEventDestroy_v2(CUevent event) {
 PFN_cuEventDestroy_v2 f=(PFN_cuEventDestroy_v2)resolve("cuEventDestroy_v2");return f?f(event):999;
}
CUresult CT_CUDA_API cuEventElapsedTime(float *out,CUevent start,CUevent end) {
 PFN_cuEventElapsedTime f=(PFN_cuEventElapsedTime)resolve("cuEventElapsedTime");
 CUresult code=f?f(out,start,end):999;
#ifdef EVENT_ZERO_TIME
 if(code==0&&out)*out=0.0f;
#endif
 return code;
}
