/* CT-owned official-Runtime-header consumer. No vendor Runtime is linked. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cuda_runtime_api.h>
#include "../include/ct_cuda.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define REQUIRE(x) do { if (!(x)) { fprintf(stderr,"contract failure at line %d\n",__LINE__); return 42; } } while(0)
#define OK(x) REQUIRE((int)(x)==0)
#define LOAD(name) PFN_##name p_##name=(PFN_##name)GetProcAddress(driver,#name); REQUIRE(p_##name!=NULL)
static int seed;
static int checked;
static DWORD WINAPI worker(void *argument) {
    int code=(int)(intptr_t)argument;
    cudaGetLastError();
    if ((int)cudaMemcpy(NULL,NULL,0,(enum cudaMemcpyKind)5)!=21) return 1;
    for(int i=0;i<100;i++) if(cudaSetDevice(0)!=cudaSuccess) return 2;
    if(cudaPeekAtLastError()!=cudaErrorInvalidMemcpyDirection) return 3;
    if(cudaGetLastError()!=cudaErrorInvalidMemcpyDirection || cudaGetLastError()!=cudaSuccess) return 4;
    if(code && cudaMemset(NULL,1,0)!=cudaSuccess) return 5;
    return 0;
}
static int interop(HMODULE driver) {
    LOAD(cuMemAlloc_v2); LOAD(cuMemFree_v2); LOAD(cuMemcpyHtoD_v2); LOAD(cuMemcpyDtoH_v2); LOAD(cuMemsetD8_v2);
    static const size_t lengths[]={17,257,4099};
    for(int t=0;t<3;t++) {
        size_t n=lengths[t]; void *a=NULL; CUdeviceptr b=0;
        unsigned char *src=(unsigned char*)VirtualAlloc(NULL,n,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
        unsigned char output[4103]; DWORD old;
        REQUIRE(src!=NULL);
        for(size_t i=0;i<n;i++) src[i]=(unsigned char)(i*37+(unsigned)seed*13);
        OK(VirtualProtect(src,n,PAGE_READONLY,&old)?0:1);
        OK(cudaMalloc(&a,n+4)); OK(p_cuMemAlloc_v2(&b,n+4));
        OK(p_cuMemsetD8_v2((CUdeviceptr)(uintptr_t)a,0xcd,n+4));
        OK(cudaMemcpy((unsigned char*)a+2,src,n,cudaMemcpyHostToDevice));
        OK(cudaMemcpy((void*)(uintptr_t)b,a,n+4,cudaMemcpyDeviceToDevice));
        memset(output,(unsigned char)((unsigned)seed*11+3),sizeof(output)); OK(p_cuMemcpyDtoH_v2(output,b,n+4));
        for(size_t i=0;i<n+4;i++) {
            unsigned char want=(i<2||i>=n+2)?0xcd:src[i-2];
            if(output[i]!=want) { fputs("oracle mismatch: copy\n",stderr); return 42; }
            checked++;
        }
        OK(p_cuMemcpyHtoD_v2((CUdeviceptr)(uintptr_t)a+2,src,n));
        OK(cudaMemset((unsigned char*)a+2,0x1234,n));
        memset(output,(unsigned char)((unsigned)seed*17+5),sizeof(output)); OK(cudaMemcpy(output,a,n+4,cudaMemcpyDeviceToHost));
        for(size_t i=0;i<n+4;i++) {
            unsigned char want=(i<2||i>=n+2)?0xcd:0x34;
            if(output[i]!=want) {fputs("oracle mismatch: fill\n",stderr);return 42;}
            checked++;
        }
        for(size_t i=0;i<n;i++) REQUIRE(src[i]==(unsigned char)(i*37+(unsigned)seed*13));
        OK(cudaDeviceSynchronize()); OK(p_cuMemFree_v2((CUdeviceptr)(uintptr_t)a)); OK(cudaFree((void*)(uintptr_t)b));
        REQUIRE(VirtualFree(src,0,MEM_RELEASE)!=0);
    }
    return 0;
}
int main(int argc,char **argv) {
    REQUIRE(argc>=3); const char *mode=argv[1]; seed=atoi(argv[2]);
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
    if(strcmp(mode,"pure_no_driver")==0) {
        unsigned char src[5]={3,9,17,42,51},dst[9]={0}; int version=-1; void *out=(void*)(uintptr_t)1;
        REQUIRE(GetModuleHandleW(L"nvcuda.dll")==NULL);
        OK(cudaMemcpy(dst+2,src,5,cudaMemcpyHostToHost)); REQUIRE(memcmp(dst+2,src,5)==0 && dst[0]==0 && dst[8]==0);
        REQUIRE((int)cudaMemcpy(NULL,NULL,0,cudaMemcpyDefault)==801);
        REQUIRE((int)cudaMemcpy(NULL,NULL,0,(enum cudaMemcpyKind)5)==21);
        REQUIRE((int)cudaMalloc(&out,0)==801 && out==NULL);
        REQUIRE((int)cudaRuntimeGetVersion(&version)==801 && version==0);
        REQUIRE((int)cudaDriverGetVersion(NULL)==1);
        REQUIRE(strcmp(cudaGetErrorName(cudaErrorIncompatibleDriverContext),"cudaErrorIncompatibleDriverContext")==0);
        REQUIRE(strcmp(cudaGetErrorString((cudaError_t)-7),"unrecognized error code")==0);
        REQUIRE((int)cudaPeekAtLastError()==1 && (int)cudaGetLastError()==1 && (int)cudaGetLastError()==0);
        OK(cudaMemset(NULL,7,0)); OK(cudaMemcpy(NULL,NULL,0,cudaMemcpyDeviceToDevice));
        REQUIRE(GetModuleHandleW(L"nvcuda.dll")==NULL);
        printf("{\"mode\":\"%s\",\"status\":\"pass\",\"checked_bytes\":5,\"observations\":1,\"seed\":%d}\n",mode,seed); return 0;
    }
    if(strcmp(mode,"wrong_driver")==0) { REQUIRE(argc==4); REQUIRE(LoadLibraryA(argv[3])!=NULL); }
    if(strcmp(mode,"missing_export")==0) { REQUIRE(LoadLibraryW(L"nvcuda.dll")!=NULL); }
    if(strcmp(mode,"missing_driver")==0||strcmp(mode,"wrong_driver")==0||strcmp(mode,"missing_export")==0) {
        int count=-1; REQUIRE((int)cudaGetDeviceCount(&count)==35 && count==0);
        count=-1; REQUIRE((int)cudaGetDeviceCount(&count)==35 && count==0);
        HMODULE loaded=GetModuleHandleW(L"nvcuda.dll");
        if(strcmp(mode,"missing_driver")==0) {REQUIRE(loaded==NULL);}
        else {typedef int (__stdcall *Counter)(void); REQUIRE(loaded!=NULL); Counter c=(Counter)GetProcAddress(loaded,"test_init_calls"); REQUIRE(c!=NULL && c()==0);}
        printf("{\"mode\":\"%s\",\"status\":\"pass\",\"checked_bytes\":0,\"observations\":2,\"seed\":%d}\n",mode,seed); return 0;
    }
    HMODULE driver=LoadLibraryW(L"nvcuda.dll"); REQUIRE(driver!=NULL);
    LOAD(cuInit); LOAD(cuDevicePrimaryCtxGetState); LOAD(cuDevicePrimaryCtxRetain); LOAD(cuDevicePrimaryCtxRelease_v2);
    LOAD(cuDevicePrimaryCtxReset_v2); LOAD(cuCtxCreate_v2); LOAD(cuCtxGetCurrent); LOAD(cuCtxDestroy_v2);
    OK(p_cuInit(0)); unsigned flags=99; int active=-1,count=-1,device=-1; CUcontext context=NULL,current=NULL;
    OK(p_cuDevicePrimaryCtxGetState(0,&flags,&active)); REQUIRE(active==0);
    OK(cudaGetDeviceCount(&count)); REQUIRE(count>0); OK(cudaGetDevice(&device)); REQUIRE(device==0);
    OK(p_cuDevicePrimaryCtxGetState(0,&flags,&active)); REQUIRE(active==0);
    if(strcmp(mode,"ordinary_context")==0) { OK(p_cuCtxCreate_v2(&context,0,0)); }
    else { OK(cudaSetDevice(0)); OK(p_cuCtxGetCurrent(&context)); REQUIRE(context!=NULL); }
    REQUIRE(GetModuleHandleW(L"nvcuda.dll")==driver);
    if(strcmp(mode,"stale_reset")==0) {
        OK(p_cuDevicePrimaryCtxReset_v2(0)); REQUIRE((int)cudaSetDevice(0)==709); REQUIRE((int)cudaDeviceSynchronize()==709);
        printf("{\"mode\":\"%s\",\"status\":\"pass\",\"checked_bytes\":0,\"observations\":3,\"seed\":%d}\n",mode,seed); return 0;
    }
    if(strcmp(mode,"threads")==0||strcmp(mode,"retain_probe")==0) {
        CUcontext external=NULL; if(strcmp(mode,"retain_probe")==0) {OK(p_cuDevicePrimaryCtxRetain(&external,0)); REQUIRE(external==context);}
        HANDLE threads[2]; threads[0]=CreateThread(NULL,0,worker,(void*)(intptr_t)1,0,NULL); threads[1]=CreateThread(NULL,0,worker,NULL,0,NULL);
        REQUIRE(threads[0]&&threads[1]); REQUIRE(WaitForMultipleObjects(2,threads,TRUE,30000)==WAIT_OBJECT_0);
        for(int i=0;i<2;i++) {DWORD exitcode=99; REQUIRE(GetExitCodeThread(threads[i],&exitcode)&&exitcode==0); CloseHandle(threads[i]);}
        if(external) {OK(p_cuDevicePrimaryCtxRelease_v2(0));OK(p_cuDevicePrimaryCtxGetState(0,&flags,&active));REQUIRE(active==1);
            OK(p_cuDevicePrimaryCtxRelease_v2(0));OK(p_cuDevicePrimaryCtxGetState(0,&flags,&active));REQUIRE(active==0);}
        printf("{\"mode\":\"%s\",\"status\":\"pass\",\"checked_bytes\":0,\"observations\":4,\"seed\":%d}\n",mode,seed); return 0;
    }
    int result=interop(driver); if(result) return result;
    OK(p_cuCtxGetCurrent(&current)); REQUIRE(current==context);
    OK(p_cuDevicePrimaryCtxGetState(0,&flags,&active));
    if(strcmp(mode,"ordinary_context")==0) { REQUIRE(active==0); OK(p_cuCtxDestroy_v2(context)); }
    else REQUIRE(active==1);
    printf("{\"mode\":\"%s\",\"status\":\"pass\",\"checked_bytes\":%d,\"observations\":5,\"seed\":%d}\n",mode,checked,seed);
    return 0;
}
