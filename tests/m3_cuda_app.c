/* Ordinary CUDA Driver ABI consumer. No CT DLL path or CT-specific loader. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ct_cuda.h"
#ifdef DYNAMIC_CUDA
struct API {
#define FIELD(name,args) PFN_##name name;
CT_DRIVER_FUNCTIONS(FIELD)
#undef FIELD
} api;
#define CALL(name) api.name
#else
#define CALL(name) name
#endif
#define CHECK(call) do { if ((call) != 0) { fputs("CUDA operation failed\n",stderr); return 3; } } while(0)
int main(int argc,char **argv) {
    const unsigned int n=257,guard=64;
    CUdevice device;CUcontext context;CUdeviceptr a,b,c;
    CUmodule module;CUfunction kernel;HMODULE driver;
    char *ptx;FILE *file=NULL;long length;unsigned int count=n,i;
    float left[257],right[257],output[321];void *arguments[4];
    wchar_t executable_path[32768],driver_path[32768],*slash;
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOOPENFILEERRORBOX);
    if(argc!=2)return 2;
#ifdef DYNAMIC_CUDA
    driver=LoadLibraryW(L"nvcuda.dll");
    if(!driver){puts("{\"status\":\"driver-unavailable\"}");return 41;}
#define RESOLVE(name,args) api.name=(PFN_##name)GetProcAddress(driver,#name);if(!api.name)return 42;
    CT_DRIVER_FUNCTIONS(RESOLVE)
#undef RESOLVE
#else
    driver=GetModuleHandleW(L"nvcuda.dll");
#endif
    /* Confirm application-local resolution without printing either path. */
    if(!driver||!GetModuleFileNameW(NULL,executable_path,32768)||!GetModuleFileNameW(driver,driver_path,32768))return 4;
    slash=wcsrchr(executable_path,L'\\');if(!slash)return 4;slash[1]=0;
    if(wcsncmp(executable_path,driver_path,wcslen(executable_path))!=0)return 5;
    if(fopen_s(&file,argv[1],"rb")||!file)return 6;
    if(fseek(file,0,SEEK_END)||(length=ftell(file))<0||length>262144){fclose(file);return 6;}
    rewind(file);ptx=(char*)malloc((size_t)length+1);if(!ptx){fclose(file);return 6;}
    if(fread(ptx,1,(size_t)length,file)!=(size_t)length){fclose(file);free(ptx);return 6;}
    fclose(file);ptx[length]=0;
    CHECK(CALL(cuInit)(0));CHECK(CALL(cuDeviceGet)(&device,0));
    CHECK(CALL(cuCtxCreate_v2)(&context,0,device));
    CHECK(CALL(cuMemAlloc_v2)(&a,sizeof(left)));CHECK(CALL(cuMemAlloc_v2)(&b,sizeof(right)));
    CHECK(CALL(cuMemAlloc_v2)(&c,sizeof(output)));
    for(i=0;i<n;++i){left[i]=(float)i*0.25f;right[i]=-(float)i*0.125f;}
    for(i=0;i<n+guard;++i)output[i]=-12345.25f;
    CHECK(CALL(cuMemcpyHtoD_v2)(a,left,sizeof(left)));CHECK(CALL(cuMemcpyHtoD_v2)(b,right,sizeof(right)));
    CHECK(CALL(cuMemcpyHtoD_v2)(c,output,sizeof(output)));
    CHECK(CALL(cuModuleLoadData)(&module,ptx));free(ptx);
    CHECK(CALL(cuModuleGetFunction)(&kernel,module,"vector_add"));
    arguments[0]=&a;arguments[1]=&b;arguments[2]=&c;arguments[3]=&count;
    CHECK(CALL(cuLaunchKernel)(kernel,5,1,1,64,1,1,0,NULL,arguments,NULL));
    CHECK(CALL(cuMemcpyDtoH_v2)(output,c,sizeof(output)));
    for(i=0;i<n;++i)if(output[i]!=left[i]+right[i])return 7;
    for(i=n;i<n+guard;++i)if(output[i]!=-12345.25f)return 8;
    CHECK(CALL(cuModuleUnload)(module));CHECK(CALL(cuMemFree_v2)(a));
    CHECK(CALL(cuMemFree_v2)(b));CHECK(CALL(cuMemFree_v2)(c));CHECK(CALL(cuCtxDestroy_v2)(context));
    puts("{\"status\":\"pass\",\"results\":257,\"guards\":64,\"application_local_driver\":true}");
    return 0;
}
