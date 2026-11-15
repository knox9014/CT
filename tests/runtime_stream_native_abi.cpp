// Official CUDA types, actual Runtime exports; no NVIDIA library linked.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cuda_runtime_api.h>
#include <cuda.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include <initializer_list>
#define REQUIRE(x) do {if (!(x)) {std::fprintf(stderr,"stream ABI line %d\n",__LINE__);return 42;}} while (0)
#define LOAD(module,name) auto p_##name=reinterpret_cast<decltype(&name)>(GetProcAddress(module,#name)); REQUIRE(p_##name)
static_assert(sizeof(cudaStream_t)==sizeof(void *),"stream ABI");
int main(int argc,char **argv) {
    REQUIRE(argc==3);
    HMODULE runtime=LoadLibraryExA(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    REQUIRE(runtime);
    auto base=reinterpret_cast<unsigned char *>(runtime);
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER *>(base);
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS64 *>(base+dos->e_lfanew);
    auto exports=reinterpret_cast<IMAGE_EXPORT_DIRECTORY *>(base+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress);
    REQUIRE(exports->NumberOfNames==40 && exports->NumberOfFunctions==40);
    LOAD(runtime,cudaStreamSynchronize); LOAD(runtime,cudaDeviceSynchronize);
    LOAD(runtime,cudaStreamCreateWithFlags); LOAD(runtime,cudaStreamDestroy);
    LOAD(runtime,cudaGetLastError); LOAD(runtime,cudaPeekAtLastError);
    LOAD(runtime,cudaGetDeviceCount); LOAD(runtime,cudaMalloc); LOAD(runtime,cudaFree);
    LOAD(runtime,cudaMemcpy); LOAD(runtime,cudaMemset);
    for (uintptr_t s : {uintptr_t(1),uintptr_t(2),uintptr_t(0x123456789),~uintptr_t(0)}) {
        REQUIRE(p_cudaStreamSynchronize(reinterpret_cast<cudaStream_t>(s))==801);
        REQUIRE(p_cudaGetLastError()==801);
    }
    REQUIRE(GetModuleHandleW(L"nvcuda.dll")==nullptr);
    if (std::strcmp(argv[2],"absent")==0) {
        for (int i=0;i<2;++i) {
            REQUIRE(p_cudaStreamSynchronize(nullptr)==35);
            REQUIRE(p_cudaGetLastError()==35);
        }
        std::puts("{\"status\":\"pass\",\"error\":35}");return 0;
    }
    int count=0;REQUIRE(p_cudaGetDeviceCount(&count)==cudaSuccess && count>0);
    HMODULE driver=GetModuleHandleW(L"nvcuda.dll");REQUIRE(driver);
    LOAD(driver,cuCtxGetCurrent);LOAD(driver,cuCtxCreate_v2);LOAD(driver,cuCtxDestroy_v2);
    LOAD(driver,cuDeviceGet);
    CUcontext initial=nullptr;REQUIRE(p_cuCtxGetCurrent(&initial)==CUDA_SUCCESS && initial==nullptr);
    CUdevice device=-1;REQUIRE(p_cuDeviceGet(&device,0)==CUDA_SUCCESS);
    const bool injected=std::strcmp(argv[2],"sync_error")==0;
    if (injected) {
        CUcontext ordinary=nullptr;REQUIRE(p_cuCtxCreate_v2(&ordinary,0,device)==CUDA_SUCCESS && ordinary);
        REQUIRE(p_cudaStreamSynchronize(nullptr)==709);
        REQUIRE(p_cudaGetLastError()==709);
        REQUIRE(p_cudaDeviceSynchronize()==709);
        REQUIRE(p_cudaGetLastError()==709);
        cudaStream_t failed=nullptr;REQUIRE(p_cudaStreamCreateWithFlags(&failed,1)==cudaSuccess && failed);
        REQUIRE(p_cudaStreamSynchronize(failed)==709);REQUIRE(p_cudaGetLastError()==709);
        REQUIRE(p_cudaStreamDestroy(failed)==709);REQUIRE(p_cudaGetLastError()==709);
        REQUIRE(p_cudaStreamSynchronize(failed)==400);REQUIRE(p_cudaGetLastError()==400);
        cudaStream_t replacement=nullptr;REQUIRE(p_cudaStreamCreateWithFlags(&replacement,0)==cudaSuccess && replacement!=failed);
        REQUIRE(p_cudaStreamDestroy(replacement)==709);REQUIRE(p_cudaGetLastError()==709);
        CUcontext after=nullptr;REQUIRE(p_cuCtxGetCurrent(&after)==CUDA_SUCCESS && after==ordinary);
        REQUIRE(p_cuCtxDestroy_v2(ordinary)==CUDA_SUCCESS);
        std::puts("{\"status\":\"pass\",\"error\":709,\"context_preserved\":true}");return 0;
    }
    REQUIRE(std::strcmp(argv[2],"positive")==0);
    REQUIRE(p_cudaStreamSynchronize(nullptr)==cudaSuccess);
    CUcontext primary=nullptr;REQUIRE(p_cuCtxGetCurrent(&primary)==CUDA_SUCCESS && primary);
    constexpr size_t n=257, bytes=n*sizeof(uint32_t);
    std::vector<uint32_t> input(n),output(n+2,0xdeadbeef);
    for (size_t i=0;i<n;++i) input[i]=static_cast<uint32_t>((i*7919)^0x8badf00d);
    void *a=nullptr,*b=nullptr;
    REQUIRE(p_cudaMalloc(&a,bytes)==cudaSuccess && a);
    REQUIRE(p_cudaMalloc(&b,bytes)==cudaSuccess && b);
    REQUIRE(p_cudaMemcpy(a,input.data(),bytes,cudaMemcpyHostToDevice)==cudaSuccess);
    REQUIRE(p_cudaStreamSynchronize(nullptr)==cudaSuccess);
    REQUIRE(p_cudaMemset(b,0,bytes)==cudaSuccess);
    REQUIRE(p_cudaMemcpy(b,a,bytes,cudaMemcpyDeviceToDevice)==cudaSuccess);
    REQUIRE(p_cudaStreamSynchronize(nullptr)==cudaSuccess);
    REQUIRE(p_cudaMemcpy(output.data()+1,b,bytes,cudaMemcpyDeviceToHost)==cudaSuccess);
    REQUIRE(p_cudaStreamSynchronize(nullptr)==cudaSuccess);
    REQUIRE(output.front()==0xdeadbeef && output.back()==0xdeadbeef);
    for (size_t i=0;i<n;++i) REQUIRE(output[i+1]==input[i]);
    CUcontext after=nullptr;REQUIRE(p_cuCtxGetCurrent(&after)==CUDA_SUCCESS && after==primary);
    REQUIRE(p_cudaFree(a)==cudaSuccess);REQUIRE(p_cudaFree(b)==cudaSuccess);
    CUcontext ordinary=nullptr;REQUIRE(p_cuCtxCreate_v2(&ordinary,0,device)==CUDA_SUCCESS && ordinary);
    REQUIRE(p_cudaStreamSynchronize(reinterpret_cast<cudaStream_t>(1))==801);
    REQUIRE(p_cudaStreamSynchronize(nullptr)==cudaSuccess);
    REQUIRE(p_cudaPeekAtLastError()==801);REQUIRE(p_cudaGetLastError()==801);
    REQUIRE(p_cuCtxGetCurrent(&after)==CUDA_SUCCESS && after==ordinary);
    REQUIRE(p_cudaDeviceSynchronize()==cudaSuccess);
    REQUIRE(p_cuCtxGetCurrent(&after)==CUDA_SUCCESS && after==ordinary);
    REQUIRE(p_cuCtxDestroy_v2(ordinary)==CUDA_SUCCESS);
    std::printf("{\"status\":\"pass\",\"checked_bytes\":%zu,\"context_preserved\":true}\n",bytes);
    return 0;
}
