// Official CUDA header function-pointer ABI; no CUDA or NVIDIA library linked.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <cuda_runtime_api.h>
#include <cuda.h>
#define REQUIRE(x) do { if (!(x)) { std::fprintf(stderr,"attribute ABI line %d\n",__LINE__); return 42; } } while (0)
#define LOAD(module, name) auto p_##name = reinterpret_cast<decltype(&name)>(GetProcAddress(module,#name)); REQUIRE(p_##name)
static_assert(sizeof(cudaDeviceAttr)==sizeof(int), "enum ABI");
static_assert(cudaDevAttrMaxThreadsPerBlock==1 && cudaDevAttrMaxBlockDimX==2 && cudaDevAttrMaxBlockDimY==3 && cudaDevAttrMaxBlockDimZ==4, "block enums");
static_assert(cudaDevAttrMaxGridDimX==5 && cudaDevAttrMaxGridDimY==6 && cudaDevAttrMaxGridDimZ==7 && cudaDevAttrComputeMode==20, "grid/mode enums");
static_assert(cudaDevAttrMaxSharedMemoryPerBlock==8, "shared memory enum");
static_assert(CU_DEVICE_ATTRIBUTE_GPU_OVERLAP==15 && CU_DEVICE_ATTRIBUTE_ASYNC_ENGINE_COUNT==40, "Driver scheduling enums");
static_assert(cudaDevAttrAsyncEngineCount==40, "Runtime async engine enum");
int main(int argc, char **argv) {
    REQUIRE(argc==3);
    HMODULE runtime=LoadLibraryExA(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    REQUIRE(runtime);
    auto image=reinterpret_cast<unsigned char *>(runtime);
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER *>(image);
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS64 *>(image+dos->e_lfanew);
    auto exports=reinterpret_cast<IMAGE_EXPORT_DIRECTORY *>(image+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress);
    REQUIRE(exports->NumberOfNames==40 && exports->NumberOfFunctions==40);
    LOAD(runtime,cudaDeviceGetAttribute); LOAD(runtime,cudaGetDeviceCount);
    LOAD(runtime,cudaPeekAtLastError); LOAD(runtime,cudaGetLastError);
    struct Guard { int before, value, after; } out={123,456,789};
    REQUIRE(p_cudaDeviceGetAttribute(nullptr,static_cast<cudaDeviceAttr>(75),-1)==1);
    REQUIRE(p_cudaGetLastError()==1);
    REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(75),-1)==101);
    for (int a : {0,9,10,11,999}) {
        REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(a),0)==801);
        REQUIRE(out.before==123 && out.value==456 && out.after==789);
    }
    REQUIRE(p_cudaGetLastError()==801);
    // Pure preflight must not load Driver, even if it exists adjacent to Runtime.
    REQUIRE(GetModuleHandleW(L"nvcuda.dll")==nullptr);
    const bool positive=std::strcmp(argv[2],"positive")==0 || std::strcmp(argv[2],"minimal")==0;
    if (!positive) {
        for (int i=0;i<3;++i) {
            REQUIRE(p_cudaDeviceGetAttribute(&out.value,cudaDevAttrMaxThreadsPerBlock,0)==35);
            REQUIRE(out.before==123 && out.value==456 && out.after==789);
            REQUIRE(p_cudaGetLastError()==35);
        }
        if (std::strcmp(argv[2],"forwarded")==0) {
            HMODULE driver=GetModuleHandleW(L"nvcuda.dll"); REQUIRE(driver);
            HMODULE foreign=GetModuleHandleW(L"foreign.dll"); REQUIRE(foreign);
            REQUIRE(GetProcAddress(driver,"cuDeviceGetAttribute")==GetProcAddress(foreign,"attribute"));
        }
        if (std::strcmp(argv[2],"missing")==0) {
            REQUIRE(GetProcAddress(GetModuleHandleW(L"nvcuda.dll"),"cuDeviceGetAttribute")==nullptr);
        }
        if (std::strcmp(argv[2],"absent")!=0) {
            int count=0; REQUIRE(p_cudaGetDeviceCount(&count)==0 && count>0);
        }
        std::puts("{\"status\":\"pass\",\"loader_error\":35}");
        return 0;
    }
    int count=0; REQUIRE(p_cudaGetDeviceCount(&count)==0 && count>0);
    HMODULE driver=GetModuleHandleW(L"nvcuda.dll"); REQUIRE(driver);
    if (std::strcmp(argv[2],"minimal")==0) {
        REQUIRE(GetProcAddress(driver,"cuModuleLoadData")==nullptr);
        REQUIRE(GetProcAddress(driver,"cuLaunchKernel")==nullptr);
    }
    LOAD(driver,cuDeviceGet); LOAD(driver,cuDeviceGetAttribute); LOAD(driver,cuCtxGetCurrent);
    CUcontext before=nullptr; REQUIRE(p_cuCtxGetCurrent(&before)==CUDA_SUCCESS && before==nullptr);
    CUdevice device=-1; REQUIRE(p_cuDeviceGet(&device,0)==CUDA_SUCCESS);
    int attrs[]={1,2,3,4,5,6,7,8,20,15,40}; int values[11]={};
    // Success preserves the preceding Runtime error.
    REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(75),0)==801);
    for (int i=0;i<11;++i) {
        int expected=-1;
        REQUIRE(p_cuDeviceGetAttribute(&expected,static_cast<CUdevice_attribute>(attrs[i]),device)==CUDA_SUCCESS);
        REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(attrs[i]),0)==cudaSuccess);
        REQUIRE(out.before==123 && out.value==expected && out.after==789);
        if (attrs[i]==8) REQUIRE(expected>=0 && expected<=16384);
        if (attrs[i]==15 || attrs[i]==40) REQUIRE(expected==0);
        REQUIRE(p_cudaPeekAtLastError()==801);
        values[i]=out.value;
    }
    CUcontext after=reinterpret_cast<CUcontext>(1); REQUIRE(p_cuCtxGetCurrent(&after)==CUDA_SUCCESS && after==before);
    out.value=456;
    REQUIRE(p_cudaDeviceGetAttribute(&out.value,cudaDevAttrMaxThreadsPerBlock,count)==101 && out.value==456);
    REQUIRE(p_cudaGetLastError()==101);
    std::printf("{\"status\":\"pass\",\"values\":[%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d],\"context_unchanged\":true}\n",values[0],values[1],values[2],values[3],values[4],values[5],values[6],values[7],values[8],values[9],values[10]);
    return 0;
}
