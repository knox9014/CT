#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "../include/ct_cudart.h"
#define REQUIRE(x) do {if(!(x)) {std::fprintf(stderr,"ABI contract line %d\n",__LINE__);return 42;}} while(0)
#define LOAD(name) auto p_##name=reinterpret_cast<decltype(&name)>(GetProcAddress(runtime,#name)); REQUIRE(p_##name!=nullptr)
struct Wrapper { unsigned magic,version;void *data;void *extra; };
int main(int argc,char **argv) {
    REQUIRE(argc==3);
    HMODULE runtime=LoadLibraryExA(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    REQUIRE(runtime!=nullptr);
    auto base=reinterpret_cast<unsigned char *>(runtime);
    auto dos=reinterpret_cast<IMAGE_DOS_HEADER *>(base);
    auto nt=reinterpret_cast<IMAGE_NT_HEADERS64 *>(base+dos->e_lfanew);
    auto exports=reinterpret_cast<IMAGE_EXPORT_DIRECTORY *>(base+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress);
    REQUIRE(exports->NumberOfNames==21&&exports->NumberOfFunctions==21);
    LOAD(__cudaRegisterFatBinary);LOAD(__cudaRegisterFatBinaryEnd);LOAD(__cudaUnregisterFatBinary);
    LOAD(__cudaRegisterFunction);LOAD(__cudaPushCallConfiguration);LOAD(__cudaPopCallConfiguration);LOAD(cudaLaunchKernel);
    LOAD(cudaGetLastError);LOAD(cudaPeekAtLastError);LOAD(cudaMalloc);LOAD(cudaFree);
    LOAD(cudaGetDeviceCount);LOAD(cudaGetDevice);LOAD(cudaSetDevice);LOAD(cudaDeviceSynchronize);
    LOAD(cudaMemcpy);LOAD(cudaMemset);LOAD(cudaGetErrorName);LOAD(cudaGetErrorString);
    LOAD(cudaDriverGetVersion);LOAD(cudaRuntimeGetVersion);
    REQUIRE(p___cudaRegisterFatBinary(nullptr)==nullptr);REQUIRE(p_cudaGetLastError()==1);
    unsigned char image[96]={};unsigned magic=0xba55ed50,header=72,metadata=64,ptx=8<<16,target=52,flags=0x41;
    uint64_t total=80,payload=8;
    std::memcpy(image,&magic,4);image[4]=1;image[6]=16;std::memcpy(image+8,&total,8);
    image[16]=1;image[18]=1;image[19]=1;std::memcpy(image+20,&header,4);std::memcpy(image+24,&payload,8);
    std::memcpy(image+36,&metadata,4);std::memcpy(image+40,&ptx,4);std::memcpy(image+44,&target,4);std::memcpy(image+56,&flags,4);image[88]='a';
    Wrapper wrapper={0x466243b1,1,image,nullptr};void **token=p___cudaRegisterFatBinary(&wrapper);REQUIRE(token!=nullptr);
    const char *host=reinterpret_cast<const char *>(uintptr_t(0x1234567891234567));char symbol[]="ct_abi_kernel";
    p___cudaRegisterFunction(token,host,symbol,symbol,-1,nullptr,nullptr,nullptr,nullptr,nullptr);
    p___cudaRegisterFatBinaryEnd(token);REQUIRE(p_cudaPeekAtLastError()==0);
    CT_dim3 grid={2,3,4},block={5,6,7},g={},b={};size_t shared=0x1122334455667788ULL;void *stream=reinterpret_cast<void *>(uintptr_t(0x8877665544332211));
    REQUIRE(p___cudaPushCallConfiguration(grid,block,0,nullptr)==0u);
    REQUIRE(p___cudaPushCallConfiguration(grid,block,1,nullptr)==801u);
    REQUIRE(p___cudaPopCallConfiguration(&g,&b,&shared,&stream)==0);
    REQUIRE(g.x==2&&g.y==3&&g.z==4&&b.x==5&&b.y==6&&b.z==7&&shared==0&&stream==nullptr);
    REQUIRE(p___cudaPopCallConfiguration(&g,&b,&shared,&stream)==9);
    REQUIRE(p_cudaGetLastError()==9);
    CT_dim3 zero={0,1,1};REQUIRE(p_cudaLaunchKernel(host,zero,block,nullptr,0,nullptr)==9);
    REQUIRE(p_cudaLaunchKernel(nullptr,grid,block,nullptr,0,nullptr)==98);
    int observations=9;
    if(std::strcmp(argv[2],"pure")!=0) {
        REQUIRE(p_cudaLaunchKernel(host,grid,block,nullptr,0,nullptr)==35);
        void *allocation=nullptr;REQUIRE(p_cudaMalloc(&allocation,8)==0&&allocation!=nullptr);REQUIRE(p_cudaFree(allocation)==0);
        observations+=3;
    }
    p___cudaUnregisterFatBinary(token);REQUIRE(p_cudaLaunchKernel(host,grid,block,nullptr,0,nullptr)==98);
    p___cudaUnregisterFatBinary(token);
    std::printf("KERNEL_NATIVE %s %d\n",argv[2],observations);
    return 0;
}
