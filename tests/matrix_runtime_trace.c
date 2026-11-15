/* Observational Driver wrapper for the pinned matrixMul EXE. No result oracle. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include "../include/ct_cuda.h"
#define cuMemAlloc_v2 forwarded_alloc
#define cuMemFree_v2 forwarded_free
#define cuMemcpyHtoD_v2 forwarded_h2d
#define cuMemcpyDtoH_v2 forwarded_dtoh
#define cuLaunchKernel forwarded_launch
#include "host_memory_driver_proxy.c"
#undef cuMemAlloc_v2
#undef cuMemFree_v2
#undef cuMemcpyHtoD_v2
#undef cuMemcpyDtoH_v2
#undef cuLaunchKernel
#ifdef MATRIX_PRODUCT_TARGET
#define MATRIX_METADATA_FLAG "false"
#else
#define MATRIX_METADATA_FLAG "true"
#endif
static CUdeviceptr allocations[3];
static size_t extents[3];
static unsigned allocated,h2d,dtoh,launches,forwarded,uploaded,freed,retired[3];
static int save(const char *name,const void *data,size_t size) {
 FILE *f=fopen(name,"wb");int ok;if(!f)return 0;
 ok=fwrite(data,1,size,f)==size;return fclose(f)==0&&ok;
}
CUresult CT_CUDA_API cuMemAlloc_v2(CUdeviceptr *pointer,size_t bytes) {
 CUresult code;PFN_cuMemsetD32_v2 fill;
 if(allocated>=3 || !bytes || bytes%4 || bytes>65536)return 999;
 code=forwarded_alloc(pointer,bytes);if(code)return code;
 allocations[allocated]=*pointer;extents[allocated++]=bytes;
 fill=(PFN_cuMemsetD32_v2)resolve("cuMemsetD32_v2");
 return fill?fill(*pointer,0x7fc00000u,bytes/4):999;
}
CUresult CT_CUDA_API cuMemcpyHtoD_v2(CUdeviceptr destination,const void *source,size_t bytes) {
 if(allocated!=3 || h2d>=2 || destination!=allocations[h2d] || bytes!=extents[h2d] || !source)return 999;
#ifndef MATRIX_NO_COPY
 {CUresult code=forwarded_h2d(destination,source,bytes);if(code)return code;uploaded++;}
#endif
 if(!save(h2d==0?"input-a.bin":"input-b.bin",source,bytes))return 999;
 h2d++;return 0;
}
CUresult CT_CUDA_API cuLaunchKernel(CUfunction function,unsigned gx,unsigned gy,unsigned gz,unsigned bx,unsigned by,unsigned bz,unsigned shared,CUstream stream,void **arguments,void **extra) {
 int k,n;
 if(allocated!=3 || h2d!=2 || launches>=301 || gz!=1 || bx!=32 || by!=32 || bz!=1 || shared || stream || extra || !arguments)return 999;
 if(!arguments[0]||!arguments[1]||!arguments[2]||!arguments[3]||!arguments[4])return 999;
 k=*(int *)arguments[3];n=*(int *)arguments[4];
 if(!((k==32 && n==32 && gx==1 && gy==1) || (k==64 && n==96 && gx==3 && gy==2)) ||
    extents[0]!=(size_t)gy*32*(unsigned)k*4 || extents[1]!=(size_t)k*(unsigned)n*4 || extents[2]!=(size_t)gy*32*(unsigned)n*4 ||
    *(CUdeviceptr *)arguments[0]!=allocations[2] || *(CUdeviceptr *)arguments[1]!=allocations[0] || *(CUdeviceptr *)arguments[2]!=allocations[1])return 999;
 launches++;
#ifdef MATRIX_NO_LAUNCH
 (void)function;return 0;
#else
 {CUresult code=forwarded_launch(function,gx,gy,gz,bx,by,bz,shared,stream,arguments,extra);if(!code)forwarded++;return code;}
#endif
}
CUresult CT_CUDA_API cuMemcpyDtoH_v2(void *destination,CUdeviceptr source,size_t bytes) {
 CUresult code;if(launches!=301 || dtoh || source!=allocations[2] || bytes!=extents[2] || !destination)return 999;
 code=forwarded_dtoh(destination,source,bytes);if(code)return code;
 if(!save("output.bin",destination,bytes))return 999;dtoh++;return 0;
}
CUresult CT_CUDA_API cuMemFree_v2(CUdeviceptr pointer) {
 unsigned i;CUresult code;for(i=0;i<3;i++)if(allocations[i]==pointer)break;
 if(i==3 || retired[i] || dtoh!=1)return 999;
 code=forwarded_free(pointer);if(code)return code;retired[i]=1;freed++;
 if(freed==3) {
  char report[256];int n=snprintf(report,sizeof(report),"{\"allocations\":%u,\"h2d\":%u,\"dtoh\":%u,\"launches\":%u,\"forwarded\":%u,\"frees\":%u,\"uploaded\":%u,\"metadata_injected\":" MATRIX_METADATA_FLAG "}",allocated,h2d,dtoh,launches,forwarded,freed,uploaded);
  if(n<0 || (size_t)n>=sizeof(report) || !save("trace.json",report,(size_t)n))return 999;
 }
 return 0;
}
