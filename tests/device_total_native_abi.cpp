// Actual provider called through official typedefs; no CUDA library link.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <cudaTypedefs.h>
#include <cstdint>
#include <cstdio>
#include <string>
#include <limits>
#include <cwchar>
static unsigned checks = 0;
#define REQUIRE(x) do { ++checks; if (!(x)) { std::fprintf(stderr,"device total check line %d\n",__LINE__); return 42; } } while(0)
#define LOAD(n,v) auto p_##n=reinterpret_cast<PFN_##v>(GetProcAddress(driver,#n)); REQUIRE(p_##n)
static std::string quote(const char *text) {
    std::string out="\""; const char *hex="0123456789abcdef";
    for (auto p=reinterpret_cast<const unsigned char *>(text);*p;++p) {
        if (*p=='"'||*p=='\\') { out+='\\';out+=static_cast<char>(*p); }
        else if (*p<32) { out+="\\u00";out+=hex[*p>>4];out+=hex[*p&15]; }
        else out+=static_cast<char>(*p);
    }
    return out+'"';
}
int wmain(int argc,wchar_t **argv) {
    REQUIRE(argc==2||argc==3);
    const bool forwarded=argc==3;
    if(forwarded) REQUIRE(std::wcscmp(argv[2],L"forwarded")==0);
    HMODULE driver=LoadLibraryExW(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);REQUIRE(driver);
    LOAD(cuInit,cuInit_v2000);LOAD(cuDriverGetVersion,cuDriverGetVersion_v2020);
    LOAD(cuDeviceGetCount,cuDeviceGetCount_v2000);LOAD(cuDeviceGetName,cuDeviceGetName_v2000);
    LOAD(cuDeviceTotalMem_v2,cuDeviceTotalMem_v3020);LOAD(cuGetProcAddress_v2,cuGetProcAddress_v12000);
    LOAD(cuCtxGetCurrent,cuCtxGetCurrent_v4000);LOAD(cuCtxCreate_v2,cuCtxCreate_v3020);LOAD(cuCtxDestroy_v2,cuCtxDestroy_v4000);
    LOAD(cuDevicePrimaryCtxGetState,cuDevicePrimaryCtxGetState_v7000);
    REQUIRE(!GetProcAddress(driver,"cuDeviceTotalMem"));
    struct Guarded { std::uint64_t before; size_t value; std::uint64_t after; } output={0x1122334455667788ULL,std::numeric_limits<size_t>::max(),0x8877665544332211ULL};
    REQUIRE(sizeof(size_t)==8);
    REQUIRE(p_cuDeviceTotalMem_v2(&output.value,0)==CUDA_ERROR_NOT_INITIALIZED&&output.value==0);
    REQUIRE(p_cuDeviceTotalMem_v2(nullptr,0)==CUDA_ERROR_INVALID_VALUE);
    REQUIRE(output.before==0x1122334455667788ULL&&output.after==0x8877665544332211ULL);
    void *function=nullptr;CUdriverProcAddressQueryResult status=CU_GET_PROC_ADDRESS_SUCCESS;
    REQUIRE(p_cuGetProcAddress_v2("cuDeviceTotalMem",&function,2000,0,&status)==0&&!function&&status==CU_GET_PROC_ADDRESS_VERSION_NOT_SUFFICIENT);
    REQUIRE(p_cuGetProcAddress_v2("cuDeviceTotalMem",&function,3019,0,&status)==0&&!function&&status==CU_GET_PROC_ADDRESS_VERSION_NOT_SUFFICIENT);
    void *expected=reinterpret_cast<void *>(p_cuDeviceTotalMem_v2);
    if(forwarded) {
        HMODULE underlying=GetModuleHandleW(L"ct_underlying.dll");REQUIRE(underlying);
        expected=reinterpret_cast<void *>(GetProcAddress(underlying,"cuDeviceTotalMem_v2"));REQUIRE(expected);
    }
    REQUIRE(p_cuGetProcAddress_v2("cuDeviceTotalMem",&function,3020,0,&status)==0&&function==expected&&status==CU_GET_PROC_ADDRESS_SUCCESS);
    REQUIRE(p_cuGetProcAddress_v2("cuDeviceTotalMem_v2",&function,3020,0,&status)==0&&!function&&status==CU_GET_PROC_ADDRESS_SYMBOL_NOT_FOUND);
    REQUIRE(p_cuInit(0)==0);
    int count=0;REQUIRE(p_cuDeviceGetCount(&count)==0&&count>0);
    char name[256]={};REQUIRE(p_cuDeviceGetName(name,256,0)==0);
    output.value=9;REQUIRE(p_cuDeviceTotalMem_v2(&output.value,-1)==CUDA_ERROR_INVALID_DEVICE&&output.value==0);
    output.value=9;REQUIRE(p_cuDeviceTotalMem_v2(&output.value,count)==CUDA_ERROR_INVALID_DEVICE&&output.value==0);
    CUcontext current=nullptr;REQUIRE(p_cuCtxGetCurrent(&current)==0&&!current);
    REQUIRE(p_cuDeviceTotalMem_v2(&output.value,0)==0&&output.value>0);
    const auto total=output.value;
    unsigned flags=99;int active=-1;REQUIRE(p_cuDevicePrimaryCtxGetState(0,&flags,&active)==0&&flags==0&&active==0);
    CUcontext ordinary=nullptr;REQUIRE(p_cuCtxCreate_v2(&ordinary,0,0)==0&&ordinary);
    REQUIRE(p_cuDeviceTotalMem_v2(&output.value,0)==0&&output.value==total);
    REQUIRE(p_cuCtxGetCurrent(&current)==0&&current==ordinary);
    REQUIRE(p_cuDevicePrimaryCtxGetState(0,&flags,&active)==0&&flags==0&&active==0);
    REQUIRE(p_cuCtxDestroy_v2(ordinary)==0);
    REQUIRE(p_cuCtxGetCurrent(&current)==0&&!current);
    REQUIRE(output.before==0x1122334455667788ULL&&output.after==0x8877665544332211ULL);
    int version=-1;REQUIRE(p_cuDriverGetVersion(&version)==CUDA_ERROR_NOT_SUPPORTED&&version==0);
    REQUIRE(FreeLibrary(driver));REQUIRE(!GetModuleHandleW(argv[1]));
    const auto device=quote(name);
    std::printf("{\"status\":\"pass\",\"checks\":%u,\"total_bytes\":%llu,\"device_name\":%s,\"tls_preserved\":true,\"canaries\":true,\"unloaded\":true,\"forwarded\":%s}\n",checks,static_cast<unsigned long long>(total),device.c_str(),forwarded?"true":"false");
    return 0;
}
