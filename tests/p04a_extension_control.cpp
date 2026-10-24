/* Typed optional-extension control using a real generated fatbin and valid args. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstdint>
#include <vector>
#include "../include/ct_cudart.h"
#define CHECK(x) do {if(!(x)){std::fprintf(stderr,"extension line %d\n",__LINE__);return 42;}}while(0)
#define LOAD(name) auto p_##name=reinterpret_cast<decltype(&name)>(GetProcAddress(runtime,#name));CHECK(p_##name)
struct Wrapper {unsigned magic,version;void *data,*extra;};
int main() {
 HMODULE runtime=LoadLibraryExW(L"cudart64_12.dll",nullptr,LOAD_LIBRARY_SEARCH_APPLICATION_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);CHECK(runtime);
 LOAD(__cudaRegisterFatBinary);LOAD(__cudaRegisterFunction);LOAD(__cudaRegisterVar);LOAD(__cudaRegisterFatBinaryEnd);LOAD(__cudaUnregisterFatBinary);
 LOAD(cudaMalloc);LOAD(cudaMemcpy);LOAD(cudaFree);LOAD(cudaLaunchKernel);LOAD(cudaGetLastError);LOAD(cudaDeviceSynchronize);
 FILE *file=nullptr;CHECK(fopen_s(&file,"global_runtime.fatbin","rb")==0&&file);CHECK(std::fseek(file,0,SEEK_END)==0);long n=std::ftell(file);CHECK(n>16&&n<=16777216);std::rewind(file);std::vector<unsigned char> image((size_t)n);CHECK(std::fread(image.data(),1,image.size(),file)==image.size());std::fclose(file);
 Wrapper wrapper={0x466243b1,1,image.data(),nullptr};void **token=p___cudaRegisterFatBinary(&wrapper);CHECK(token);
 auto host=reinterpret_cast<const char *>(uintptr_t(0x1234567812345678));char symbol[]="ct_read",global[]="ct_counter";char host_global;
 p___cudaRegisterFunction(token,host,symbol,symbol,-1,nullptr,nullptr,nullptr,nullptr,nullptr);
 p___cudaRegisterVar(token,&host_global,global,global,0,4,0,0);p___cudaRegisterFatBinaryEnd(token);
 unsigned input[17]={},output[17]={};void *di=nullptr,*out=nullptr;
 CHECK(p_cudaMalloc(&di,sizeof(input))==0);CHECK(p_cudaMalloc(&out,sizeof(output))==0);
 CHECK(p_cudaMemcpy(di,input,sizeof(input),1)==0);CHECK(p_cudaMemcpy(out,output,sizeof(output),1)==0);
 uint64_t a=(uint64_t)(uintptr_t)out,b=(uint64_t)(uintptr_t)di;unsigned count=17,bias=0;void *args[]={&a,&b,&count,&bias};CT_dim3 grid={1,1,1},block={32,1,1};
 int error=p_cudaLaunchKernel(host,grid,block,args,0,nullptr);CHECK(error==35);CHECK(p_cudaGetLastError()==35);
 CHECK(p_cudaMemcpy(output,out,sizeof(output),2)==0);for(unsigned v:output)CHECK(v==0);
 CHECK(p_cudaFree(di)==0);CHECK(p_cudaFree(out)==0);p___cudaUnregisterFatBinary(token);CHECK(p_cudaDeviceSynchronize()==0);
 std::printf("{\"error\":%d,\"memory_roundtrip\":1}\n",error);return 0;
}
