// Actual DLL calls through official CUDA header types.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cuda_runtime_api.h>
#include <cuda.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#define REQUIRE(x) do{if(!(x)){std::fprintf(stderr,"host ABI line %d\n",__LINE__);return 42;}}while(0)
#define LOAD(module,name) auto p_##name=reinterpret_cast<decltype(&name)>(GetProcAddress(module,#name));REQUIRE(p_##name)
int main(int argc,char **argv) {
    REQUIRE(argc==3);HMODULE rt=LoadLibraryExA(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);REQUIRE(rt);
    auto base=reinterpret_cast<unsigned char *>(rt);auto dos=reinterpret_cast<IMAGE_DOS_HEADER *>(base);
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS64 *>(base+dos->e_lfanew);
    auto exports=reinterpret_cast<IMAGE_EXPORT_DIRECTORY *>(base+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress);
    REQUIRE(exports->NumberOfNames==40 && exports->NumberOfFunctions==40);
    LOAD(rt,cudaHostAlloc);LOAD(rt,cudaFreeHost);LOAD(rt,cudaGetLastError);LOAD(rt,cudaPeekAtLastError);
    LOAD(rt,cudaMalloc);LOAD(rt,cudaFree);LOAD(rt,cudaMemcpy);LOAD(rt,cudaGetDeviceCount);
    void *out=reinterpret_cast<void *>(uintptr_t(123));
    REQUIRE(p_cudaHostAlloc(nullptr,4,0)==1);REQUIRE(p_cudaGetLastError()==1);
    REQUIRE(p_cudaHostAlloc(&out,0,0)==1 && out==reinterpret_cast<void *>(uintptr_t(123)));
    for(unsigned flag:{1u,2u,3u,4u,5u,6u,7u,8u,0xffffffffu}) {
        REQUIRE(p_cudaHostAlloc(&out,4,flag)==(flag<=7?801:1));
        REQUIRE(out==reinterpret_cast<void *>(uintptr_t(123)));
    }
    REQUIRE(p_cudaFreeHost(nullptr)==1);REQUIRE(p_cudaGetLastError()==1);
    REQUIRE(GetModuleHandleW(L"nvcuda.dll")==nullptr);
    if(std::strcmp(argv[2],"positive")!=0) {
        for(int i=0;i<2;++i){REQUIRE(p_cudaHostAlloc(&out,4,0)==35);REQUIRE(out==reinterpret_cast<void *>(uintptr_t(123)));REQUIRE(p_cudaGetLastError()==35);}
        if(std::strcmp(argv[2],"absent")!=0){
            int count=0;REQUIRE(p_cudaGetDeviceCount(&count)==0 && count>0);
            void *device=nullptr;REQUIRE(p_cudaMalloc(&device,16)==0 && device);REQUIRE(p_cudaFree(device)==0);
            HMODULE driver=GetModuleHandleW(L"nvcuda.dll");REQUIRE(driver);
            if(std::strstr(argv[2],"forwarded")!=nullptr){
                HMODULE foreign=GetModuleHandleW(L"host_foreign.dll");REQUIRE(foreign);
                const char *name=std::strstr(argv[2],"alloc")?"cuMemHostAlloc":"cuMemFreeHost";
                REQUIRE(GetProcAddress(driver,name)==GetProcAddress(foreign,name));
            }
        }
        std::puts("{\"status\":\"pass\",\"error\":35}");return 0;
    }
    // Invalid preflight left TLS error1; success must not clear it.
    constexpr size_t n=257,bytes=(n+2)*sizeof(uint32_t);
    void *ha=nullptr,*hb=nullptr,*device=nullptr;
    REQUIRE(p_cudaHostAlloc(&ha,bytes,0)==0 && ha);REQUIRE(p_cudaPeekAtLastError()==0);
    REQUIRE(p_cudaHostAlloc(&hb,bytes,0)==0 && hb);
    auto a=static_cast<uint32_t *>(ha);auto b=static_cast<uint32_t *>(hb);
    for(size_t i=0;i<n+2;++i){a[i]=0xdeadbeef;b[i]=0xdeadbeef;}
    for(size_t i=0;i<n;++i)a[i+1]=static_cast<uint32_t>(i*7919)^0xbadc0ffe;
    REQUIRE(p_cudaMalloc(&device,n*sizeof(uint32_t))==0 && device);
    REQUIRE(p_cudaMemcpy(device,a+1,n*sizeof(uint32_t),cudaMemcpyHostToDevice)==0);
    REQUIRE(p_cudaMemcpy(b+1,device,n*sizeof(uint32_t),cudaMemcpyDeviceToHost)==0);
    REQUIRE(a[0]==0xdeadbeef && a[n+1]==0xdeadbeef && b[0]==0xdeadbeef && b[n+1]==0xdeadbeef);
    for(size_t i=0;i<n;++i)REQUIRE(a[i+1]==b[i+1]);
    HMODULE driver=GetModuleHandleW(L"nvcuda.dll");REQUIRE(driver);
    LOAD(driver,cuPointerGetAttribute);LOAD(driver,cuMemGetAddressRange_v2);
    LOAD(driver,cuCtxGetCurrent);LOAD(driver,cuCtxCreate_v2);LOAD(driver,cuCtxSetCurrent);LOAD(driver,cuCtxDestroy_v2);LOAD(driver,cuDeviceGet);
    int memory=-1;REQUIRE(p_cuPointerGetAttribute(&memory,CU_POINTER_ATTRIBUTE_MEMORY_TYPE,reinterpret_cast<CUdeviceptr>(ha))==CUDA_ERROR_NOT_SUPPORTED && memory==-1);
    CUdeviceptr range=0;size_t extent=0;REQUIRE(p_cuMemGetAddressRange_v2(&range,&extent,reinterpret_cast<CUdeviceptr>(ha))==CUDA_ERROR_NOT_FOUND && range==0 && extent==0);
    REQUIRE(p_cudaFree(ha)==1);REQUIRE(p_cudaFreeHost(a+1)==1);
    CUcontext primary=nullptr,ordinary=nullptr;REQUIRE(p_cuCtxGetCurrent(&primary)==CUDA_SUCCESS && primary);
    CUdevice dev=-1;REQUIRE(p_cuDeviceGet(&dev,0)==CUDA_SUCCESS);REQUIRE(p_cuCtxCreate_v2(&ordinary,0,dev)==CUDA_SUCCESS);
    REQUIRE(p_cudaFreeHost(ha)==1);REQUIRE(p_cuCtxSetCurrent(primary)==CUDA_SUCCESS);
    REQUIRE(p_cuCtxDestroy_v2(ordinary)==CUDA_SUCCESS);
    REQUIRE(p_cudaFreeHost(ha)==0);REQUIRE(p_cudaFreeHost(ha)==1);
    REQUIRE(p_cudaFreeHost(hb)==0);REQUIRE(p_cudaFree(device)==0);
    REQUIRE(p_cudaGetLastError()==1);
    std::puts("{\"status\":\"pass\",\"checked_bytes\":1028,\"host_allocations\":2,\"guards\":true}");return 0;
}
