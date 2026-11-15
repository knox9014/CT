// Official CUDA types for preflight and benign asynchronous Driver rejection.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cuda_runtime_api.h>
#include <cuda.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#define REQUIRE(x) do{if(!(x)){std::fprintf(stderr,"async ABI line %d\n",__LINE__);return 42;}}while(0)
#define LOAD(module,name) auto p_##name=reinterpret_cast<decltype(&name)>(GetProcAddress(module,#name));REQUIRE(p_##name)
int main(int argc,char **argv){
    REQUIRE(argc==3);HMODULE rt=LoadLibraryExA(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);REQUIRE(rt);
    auto base=reinterpret_cast<unsigned char *>(rt);auto dos=reinterpret_cast<IMAGE_DOS_HEADER *>(base);
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS64 *>(base+dos->e_lfanew);
    auto exports=reinterpret_cast<IMAGE_EXPORT_DIRECTORY *>(base+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress);
    REQUIRE(exports->NumberOfNames==40&&exports->NumberOfFunctions==40);
    LOAD(rt,cudaMemcpyAsync);LOAD(rt,cudaHostAlloc);LOAD(rt,cudaFreeHost);LOAD(rt,cudaMalloc);LOAD(rt,cudaFree);
    LOAD(rt,cudaStreamCreateWithFlags);LOAD(rt,cudaStreamSynchronize);LOAD(rt,cudaStreamDestroy);
    LOAD(rt,cudaGetLastError);LOAD(rt,cudaPeekAtLastError);
    REQUIRE(p_cudaMemcpyAsync(nullptr,nullptr,0,static_cast<cudaMemcpyKind>(-1),nullptr)==21);
    REQUIRE(p_cudaMemcpyAsync(nullptr,nullptr,0,cudaMemcpyDefault,nullptr)==801);
    REQUIRE(p_cudaMemcpyAsync(nullptr,nullptr,0,cudaMemcpyHostToHost,nullptr)==801);
    REQUIRE(p_cudaMemcpyAsync(nullptr,nullptr,0,cudaMemcpyHostToDevice,reinterpret_cast<cudaStream_t>(1))==801);
    REQUIRE(p_cudaMemcpyAsync(nullptr,nullptr,4,cudaMemcpyHostToDevice,nullptr)==1);
    REQUIRE(p_cudaMemcpyAsync(nullptr,nullptr,0,cudaMemcpyHostToDevice,nullptr)==0);
    REQUIRE(p_cudaPeekAtLastError()==1);REQUIRE(p_cudaGetLastError()==1);
    REQUIRE(GetModuleHandleW(L"nvcuda.dll")==nullptr);
    if(std::strcmp(argv[2],"absent")==0){
        REQUIRE(p_cudaMemcpyAsync(reinterpret_cast<void *>(uintptr_t(0x4000)),reinterpret_cast<void *>(uintptr_t(0x8000)),4,cudaMemcpyDeviceToDevice,nullptr)==35);
        REQUIRE(p_cudaGetLastError()==35);std::puts("{\"status\":\"pass\",\"error\":35}");return 0;
    }
    REQUIRE(std::strcmp(argv[2],"rejected_copy")==0);
    void *host=nullptr,*device=nullptr;cudaStream_t stream=nullptr;
    REQUIRE(p_cudaHostAlloc(&host,64,0)==0&&host);REQUIRE(p_cudaMalloc(&device,64)==0&&device);
    REQUIRE(p_cudaStreamCreateWithFlags(&stream,1)==0&&stream);
    HMODULE driver=GetModuleHandleW(L"nvcuda.dll");REQUIRE(driver);
    LOAD(driver,cuMemFreeHost);LOAD(driver,cuMemFree_v2);LOAD(driver,cuCtxGetCurrent);
    CUcontext before=nullptr;REQUIRE(p_cuCtxGetCurrent(&before)==CUDA_SUCCESS&&before);
    // One-past an owned device allocation is rejected before any GPU command.
    void *invalid=reinterpret_cast<void *>(reinterpret_cast<uintptr_t>(device)+64);
    REQUIRE(p_cudaMemcpyAsync(invalid,host,4,cudaMemcpyHostToDevice,stream)==0);
    REQUIRE(p_cudaStreamSynchronize(stream)==1);REQUIRE(p_cudaGetLastError()==1);
    // Cleanup executes, then reports the prior queued error. Raw Driver re-free
    // must reject: success here would mean the Runtime failed to free storage.
    REQUIRE(p_cudaFreeHost(host)==1);REQUIRE(p_cuMemFreeHost(host)==CUDA_ERROR_INVALID_VALUE);
    REQUIRE(p_cudaFree(device)==1);REQUIRE(p_cuMemFree_v2(reinterpret_cast<CUdeviceptr>(device))==CUDA_ERROR_INVALID_VALUE);
    REQUIRE(p_cudaStreamDestroy(stream)==1);REQUIRE(p_cudaStreamDestroy(stream)==400);
    CUcontext after=nullptr;REQUIRE(p_cuCtxGetCurrent(&after)==CUDA_SUCCESS&&after==before);
    std::puts("{\"status\":\"pass\",\"error\":1,\"cleanup\":true,\"context_preserved\":true}");return 0;
}
