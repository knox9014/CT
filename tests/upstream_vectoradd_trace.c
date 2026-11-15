/* Observational forwarding provider for one original, single-thread vectorAdd run.
   Raw arrays remain in the ignored isolated bundle. No expected sums computed. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include "../include/ct_cuda.h"
#define cuInit forwarded_init
#define cuMemAlloc_v2 forwarded_alloc
#define cuMemFree_v2 forwarded_free
#define cuMemcpyHtoD_v2 forwarded_h2d
#define cuMemcpyDtoH_v2 forwarded_dtoh
#define cuLaunchKernel forwarded_launch
#include "p04a_noop_driver.c"
#undef cuInit
#undef cuMemAlloc_v2
#undef cuMemFree_v2
#undef cuMemcpyHtoD_v2
#undef cuMemcpyDtoH_v2
#undef cuLaunchKernel
static CUdeviceptr allocations[3];
static unsigned allocated,h2d,dtoh,launches,forwarded,freed,retired[3];
static char device_name[256];
static int save(const char *name,const void *data,size_t size) {
 FILE *f=fopen(name,"wb");int ok;if(!f)return 0;
 ok=fwrite(data,1,size,f)==size;return fclose(f)==0&&ok;
}
CUresult CT_CUDA_API cuInit(unsigned flags) {
 CUresult code=forwarded_init(flags);PFN_cuDeviceGetName name;
 if(code)return code;name=(PFN_cuDeviceGetName)resolve("cuDeviceGetName");
 return name?name(device_name,sizeof(device_name),0):999;
}
CUresult CT_CUDA_API cuMemAlloc_v2(CUdeviceptr *pointer,size_t bytes) {
 CUresult code;PFN_cuMemsetD32_v2 fill;
 if(allocated>=3||bytes!=200000)return 999;
 code=forwarded_alloc(pointer,bytes);if(code)return code;
 allocations[allocated++]=*pointer;fill=(PFN_cuMemsetD32_v2)resolve("cuMemsetD32_v2");
 return fill?fill(*pointer,0x7fc00000u,50000):999;
}
CUresult CT_CUDA_API cuMemcpyHtoD_v2(CUdeviceptr destination,const void *source,size_t bytes) {
 CUresult code;if(allocated!=3||h2d>=2||destination!=allocations[h2d]||bytes!=200000||!source)return 999;
 code=forwarded_h2d(destination,source,bytes);if(code)return code;
 if(!save(h2d==0?"input-a.bin":"input-b.bin",source,bytes))return 999;
 h2d++;return 0;
}
CUresult CT_CUDA_API cuLaunchKernel(CUfunction function,unsigned gx,unsigned gy,unsigned gz,unsigned bx,unsigned by,unsigned bz,unsigned shared,CUstream stream,void **arguments,void **extra) {
 if(allocated!=3||h2d!=2||launches||gx!=196||gy!=1||gz!=1||bx!=256||by!=1||bz!=1||shared||stream||extra||!arguments)return 999;
 if(!arguments[0]||!arguments[1]||!arguments[2]||!arguments[3]||
    *(CUdeviceptr *)arguments[0]!=allocations[0]||*(CUdeviceptr *)arguments[1]!=allocations[1]||
    *(CUdeviceptr *)arguments[2]!=allocations[2]||*(unsigned *)arguments[3]!=50000)return 999;
 launches++;
#ifdef TRACE_NOOP
 (void)function;return 0;
#else
 forwarded++;return forwarded_launch(function,gx,gy,gz,bx,by,bz,shared,stream,arguments,extra);
#endif
}
CUresult CT_CUDA_API cuMemcpyDtoH_v2(void *destination,CUdeviceptr source,size_t bytes) {
 CUresult code;if(launches!=1||dtoh||source!=allocations[2]||bytes!=200000||!destination)return 999;
 code=forwarded_dtoh(destination,source,bytes);if(code)return code;
 if(!save("output.bin",destination,bytes))return 999;
 dtoh++;return 0;
}
CUresult CT_CUDA_API cuMemFree_v2(CUdeviceptr pointer) {
 unsigned i;CUresult code;for(i=0;i<3;i++)if(allocations[i]==pointer)break;
 if(i==3||retired[i]||dtoh!=1)return 999;
 code=forwarded_free(pointer);if(code)return code;retired[i]=1;freed++;
 if(freed==3) {
  char report[512];int n=snprintf(report,sizeof(report),"{\"device\":\"%s\",\"allocations\":%u,\"h2d\":%u,\"dtoh\":%u,\"launches\":%u,\"forwarded\":%u,\"frees\":%u,\"bytes\":200000}",device_name,allocated,h2d,dtoh,launches,forwarded,freed);
  if(n<0||(size_t)n>=sizeof(report)||!save("trace.json",report,(size_t)n))return 999;
 }
 return 0;
}
