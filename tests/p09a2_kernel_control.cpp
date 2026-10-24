/* Supplemental explicit-retirement control, not the genuine-nvcc primary path. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "../include/ct_cudart.h"
#define REQUIRE(x) do{if(!(x)){std::fprintf(stderr,"retire contract line %d\n",__LINE__);return 42;}}while(0)
#define LOAD(name) auto p_##name=reinterpret_cast<decltype(&name)>(GetProcAddress(runtime,#name));REQUIRE(p_##name!=nullptr)
#define OK(x) REQUIRE((x)==0)
struct Wrapper {unsigned magic,version;void *data,*extra;};
static void array(const unsigned *p){std::putchar('[');for(int i=0;i<21;++i){if(i)std::putchar(',');std::printf("%u",p[i]);}std::putchar(']');}
int main(int argc,char **argv) {
    REQUIRE(argc==3);unsigned seed=(unsigned)std::strtoul(argv[2],nullptr,10);REQUIRE(seed>0&&seed<=1000000);
    HMODULE runtime=LoadLibraryExW(L"cudart64_12.dll",nullptr,LOAD_LIBRARY_SEARCH_APPLICATION_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);REQUIRE(runtime);
    LOAD(__cudaRegisterFatBinary);LOAD(__cudaRegisterFunction);LOAD(__cudaRegisterFatBinaryEnd);LOAD(__cudaUnregisterFatBinary);
    LOAD(cudaLaunchKernel);LOAD(cudaMalloc);LOAD(cudaMemcpy);LOAD(cudaFree);LOAD(cudaDeviceSynchronize);LOAD(cudaGetLastError);
    FILE *file=nullptr;REQUIRE(fopen_s(&file,"kernel_oracle.fatbin","rb")==0&&file);
    REQUIRE(std::fseek(file,0,SEEK_END)==0);long size=std::ftell(file);REQUIRE(size>=16&&size<=16*1024*1024);
    std::rewind(file);std::vector<unsigned char> image((size_t)size);REQUIRE(std::fread(image.data(),1,image.size(),file)==image.size());std::fclose(file);
    Wrapper wrapper={0x466243b1,1,image.data(),nullptr};void **token=p___cudaRegisterFatBinary(&wrapper);REQUIRE(token);
    auto host=reinterpret_cast<const char *>(uintptr_t(0x1234567891234567));char symbol[]="ct_oracle_add";
    p___cudaRegisterFunction(token,host,symbol,symbol,-1,nullptr,nullptr,nullptr,nullptr,nullptr);p___cudaRegisterFatBinaryEnd(token);
    std::memset(image.data(),0,image.size());std::memset(symbol,'x',sizeof(symbol));
    unsigned a[21],b[21],c[21];void *da=nullptr,*db=nullptr,*dc=nullptr;
    for(unsigned i=0;i<21;++i){a[i]=b[i]=0xdecafbad;c[i]=0xa5a5a5a5;}
    for(unsigned i=0;i<17;++i){a[i+2]=seed*13+i*37;b[i+2]=seed*17+i*19;}
    OK(p_cudaMalloc(&da,sizeof(a)));OK(p_cudaMalloc(&db,sizeof(b)));OK(p_cudaMalloc(&dc,sizeof(c)));
    OK(p_cudaMemcpy(da,a,sizeof(a),1));OK(p_cudaMemcpy(db,b,sizeof(b),1));OK(p_cudaMemcpy(dc,c,sizeof(c),1));
    uint64_t pa=(uint64_t)(uintptr_t)da+8,pb=(uint64_t)(uintptr_t)db+8,pc=(uint64_t)(uintptr_t)dc+8;unsigned n=17;
    void *args[]={&pa,&pb,&pc,&n};CT_dim3 grid={2,1,1},block={16,1,1};
    OK(p_cudaLaunchKernel(host,grid,block,args,0,nullptr));
    p___cudaUnregisterFatBinary(token);
    int retired=p_cudaLaunchKernel(host,grid,block,args,0,nullptr);REQUIRE(retired==98);
    OK(p_cudaDeviceSynchronize());REQUIRE(p_cudaGetLastError()==98);p___cudaUnregisterFatBinary(token);
    OK(p_cudaMemcpy(a,da,sizeof(a),2));OK(p_cudaMemcpy(b,db,sizeof(b),2));OK(p_cudaMemcpy(c,dc,sizeof(c),2));
    OK(p_cudaFree(da));OK(p_cudaFree(db));OK(p_cudaFree(dc));OK(p_cudaDeviceSynchronize());
    std::printf("{\"seed\":%u,\"mode\":\"retire\",\"errors\":[%d],\"runs\":[{\"seed\":%u,\"a\":",seed,retired,seed);
    array(a);std::printf(",\"b\":");array(b);std::printf(",\"c\":");array(c);std::puts("}]}");return 0;
}
