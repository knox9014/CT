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
    CUdevice context_device;
    int verify_device;
    CUmodule module;CUfunction kernel;HMODULE driver;
    char *ptx;FILE *file=NULL;long length;unsigned int count=n,i;
    char device_name[256]={0};
    float left[257],right[257],output[321];void *arguments[4];
    wchar_t executable_path[32768],driver_path[32768],*slash;
    DWORD executable_length, driver_length;
#ifdef DYNAMIC_CUDA
    PFN_cuFuncGetParamInfo get_info;
#endif
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOOPENFILEERRORBOX);
    if(argc!=2)return 2;
#ifdef DYNAMIC_CUDA
    driver=LoadLibraryW(L"nvcuda.dll");
    if(!driver){puts("{\"status\":\"driver-unavailable\"}");return 41;}
#else
    driver=GetModuleHandleW(L"nvcuda.dll");
#endif
    /* Confirm application-local resolution without printing either path. */
    if (!driver) return 4;
    executable_length = GetModuleFileNameW(NULL, executable_path, _countof(executable_path));
    driver_length = GetModuleFileNameW(driver, driver_path, _countof(driver_path));
    if (!executable_length || executable_length >= _countof(executable_path) ||
        !driver_length || driver_length >= _countof(driver_path)) return 4;
    slash = wcsrchr(executable_path, L'\\');
    if (!slash || wcscpy_s(slash + 1, _countof(executable_path) -
        (size_t)(slash + 1 - executable_path), L"nvcuda.dll")) return 4;
    if (CompareStringOrdinal(executable_path, -1, driver_path, -1, TRUE) != CSTR_EQUAL) return 5;
#ifdef DYNAMIC_CUDA
#define RESOLVE(name,args) api.name=(PFN_##name)GetProcAddress(driver,#name);if(!api.name)return 42;
    CT_DRIVER_FUNCTIONS(RESOLVE)
#undef RESOLVE
#endif
    if(fopen_s(&file,argv[1],"rb")||!file)return 6;
    if(fseek(file,0,SEEK_END)||(length=ftell(file))<0||length>262144){fclose(file);return 6;}
    rewind(file);ptx=(char*)malloc((size_t)length+1);if(!ptx){fclose(file);return 6;}
    if(fread(ptx,1,(size_t)length,file)!=(size_t)length){fclose(file);free(ptx);return 6;}
    fclose(file);ptx[length]=0;
    CHECK(CALL(cuInit)(0));
    verify_device = GetEnvironmentVariableW(L"CT_M3_DEVICE_UUID", NULL, 0) != 0;
    if (verify_device) {
        typedef int (WINAPI *ResolveDevice)(CUdevice *);
        ResolveDevice resolve = (ResolveDevice)GetProcAddress(driver, "ctM3ResolveDevice");
        if (!resolve || resolve(&device) != 0) {
            free(ptx);
            fputs("Selected Intel GPU is unavailable or ambiguous\n", stderr);
            return 10;
        }
    } else {
        CHECK(CALL(cuDeviceGet)(&device,0));
    }
    CHECK(CALL(cuDeviceGetName)(device_name,(int)sizeof(device_name),device));
    if(!device_name[0]||!memchr(device_name,0,sizeof(device_name)))return 9;
    CHECK(CALL(cuCtxCreate_v2)(&context,0,device));
    if (verify_device) {
        CHECK(CALL(cuCtxGetDevice)(&context_device));
        if (context_device != device) return 10;
    }
    CHECK(CALL(cuMemAlloc_v2)(&a,sizeof(left)));CHECK(CALL(cuMemAlloc_v2)(&b,sizeof(right)));
    CHECK(CALL(cuMemAlloc_v2)(&c,sizeof(output)));
    for(i=0;i<n;++i){left[i]=(float)i*0.25f;right[i]=-(float)i*0.125f;}
    for(i=0;i<n+guard;++i)output[i]=-12345.25f;
    CHECK(CALL(cuMemcpyHtoD_v2)(a,left,sizeof(left)));CHECK(CALL(cuMemcpyHtoD_v2)(b,right,sizeof(right)));
    CHECK(CALL(cuMemcpyHtoD_v2)(c,output,sizeof(output)));
    CHECK(CALL(cuModuleLoadData)(&module,ptx));free(ptx);
    CHECK(CALL(cuModuleGetFunction)(&kernel,module,"vector_add"));
    arguments[0]=&a;arguments[1]=&b;arguments[2]=&c;arguments[3]=&count;
#ifdef DYNAMIC_CUDA
    {
        /* One allocation for the option list, size and payload, as in the
           pinned tinygrad CUDA backend. The size excludes the header. */
        struct {
            void *extra[5];
            size_t size;
            unsigned char packed[28];
        } launch = {0};
        const size_t widths[] = {8,8,8,4};
        size_t offset, width;
        void **extra = launch.extra;
        void *resolved = NULL;
        int status = -1;
        extra[0] = (void *)1;
        extra[1] = launch.packed;
        extra[2] = (void *)2;
        extra[3] = &launch.size;
        launch.size = sizeof(launch.packed);
        CHECK(CALL(cuGetProcAddress_v2)("cuFuncGetParamInfo",&resolved,12090,0,&status));
        get_info = (PFN_cuFuncGetParamInfo)resolved;
        if (!get_info || status != 0 || get_info != CALL(cuFuncGetParamInfo)) return 14;
        /* Like a diagnostic consumer, enumerate until the query fails. */
        for (i=0;(status=get_info(kernel,i,&offset,&width))==0;++i) {
            if (i >= _countof(widths) || offset != i*8 || width != widths[i]) return 15;
            memcpy(launch.packed+offset,arguments[i],width);
        }
        if (status != 1 || i != _countof(widths)) return 16;
        CHECK(get_info(kernel,3,&offset,NULL));
        if (offset != 24 || get_info(kernel,0,NULL,&width) != 1) return 16;
        if (CALL(cuLaunchKernel)(kernel,5,1,1,64,1,1,0,NULL,arguments,extra) != 1) return 11;
        --launch.size;
        if (CALL(cuLaunchKernel)(kernel,5,1,1,64,1,1,0,NULL,NULL,extra) != 1) return 12;
        ++launch.size;
        extra[2] = (void *)1;
        if (CALL(cuLaunchKernel)(kernel,5,1,1,64,1,1,0,NULL,NULL,extra) != 1) return 13;
        extra[2] = (void *)2;
        CHECK(CALL(cuLaunchKernel)(kernel,5,1,1,64,1,1,0,NULL,NULL,extra));
    }
#else
    CHECK(CALL(cuLaunchKernel)(kernel,5,1,1,64,1,1,0,NULL,arguments,NULL));
#endif
    CHECK(CALL(cuMemcpyDtoH_v2)(output,c,sizeof(output)));
    for(i=0;i<n;++i)if(output[i]!=left[i]+right[i])return 7;
    for(i=n;i<n+guard;++i)if(output[i]!=-12345.25f)return 8;
    CHECK(CALL(cuModuleUnload)(module));CHECK(CALL(cuMemFree_v2)(a));
#ifdef DYNAMIC_CUDA
    {
        size_t offset, width;
        if (get_info(kernel,0,&offset,&width) != 400) return 17;
    }
#endif
    CHECK(CALL(cuMemFree_v2)(b));CHECK(CALL(cuMemFree_v2)(c));CHECK(CALL(cuCtxDestroy_v2)(context));
    /* Keep the JSON valid for GPU names containing quotes or non-ASCII bytes. */
    fputs("{\"status\":\"pass\",\"results\":257,\"guards\":64,\"application_local_driver\":true,\"device_name_hex\":\"",stdout);
    for(i=0;device_name[i];++i)printf("%02x",(unsigned int)(unsigned char)device_name[i]);
    printf("\",\"device_verified\":%s}\n", verify_device ? "true" : "false");
    return 0;
}
