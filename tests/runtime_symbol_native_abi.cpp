/* Calls actual Runtime exports using original CUDA header function-pointer types. */
#include <cuda_runtime_api.h>
#include <math.h>
#include <string.h>
#define __CUDA_INTERNAL_COMPILATION__
#define __CUDA_INCLUDE_COMPILER_INTERNAL_HEADERS__
#include <crt/host_runtime.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstdint>
#include <vector>
#include <cstring>
#define CHECK(x) do{if(!(x)){std::fprintf(stderr,"symbol ABI line %d\n",__LINE__);return 42;}}while(0)
#define LOAD(name) auto p_##name=reinterpret_cast<decltype(&name)>(GetProcAddress(runtime,#name));CHECK(p_##name)
struct Wrapper {unsigned magic,version;void *data,*extra;};
int main(int argc,char **argv) {
 CHECK(argc==3);HMODULE runtime=LoadLibraryExA(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);CHECK(runtime);
 auto base=reinterpret_cast<unsigned char *>(runtime);auto dos=reinterpret_cast<IMAGE_DOS_HEADER *>(base);auto nt=reinterpret_cast<IMAGE_NT_HEADERS64 *>(base+dos->e_lfanew);
 auto exports=reinterpret_cast<IMAGE_EXPORT_DIRECTORY *>(base+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress);CHECK(exports->NumberOfNames==26&&exports->NumberOfFunctions==26);
 LOAD(cudaGetSymbolAddress);LOAD(cudaGetSymbolSize);LOAD(cudaMemcpyToSymbol);LOAD(cudaMemcpyFromSymbol);LOAD(cudaGetLastError);
 LOAD(cudaMalloc);LOAD(cudaFree);LOAD(cudaMemcpy);LOAD(cudaDeviceSynchronize);
 LOAD(__cudaRegisterFatBinary);LOAD(__cudaRegisterFatBinaryEnd);LOAD(__cudaRegisterVar);LOAD(__cudaUnregisterFatBinary);
 void *address=reinterpret_cast<void *>(uintptr_t(8192));size_t size=123;
 CHECK(p_cudaGetSymbolAddress(&address,nullptr)==cudaErrorInvalidSymbol&&address==reinterpret_cast<void *>(uintptr_t(8192)));
 CHECK(p_cudaGetSymbolSize(&size,nullptr)==cudaErrorInvalidSymbol&&size==123);
 CHECK(p_cudaMemcpyToSymbol(nullptr,nullptr,0,0,cudaMemcpyHostToHost)==cudaErrorInvalidMemcpyDirection);
 CHECK(p_cudaMemcpyFromSymbol(nullptr,nullptr,0,0,cudaMemcpyDefault)==cudaErrorNotSupported);
 CHECK(p_cudaGetSymbolAddress(nullptr,nullptr)==cudaErrorInvalidValue);
 CHECK(p_cudaGetSymbolSize(nullptr,nullptr)==cudaErrorInvalidValue);
 CHECK(p_cudaMemcpyToSymbol(nullptr,nullptr,1,0,cudaMemcpyHostToDevice)==cudaErrorInvalidValue);
 p_cudaGetLastError();
 if(std::strcmp(argv[2],"pure")==0){std::printf("SYMBOL_NATIVE pure 26 13 21 801\n");return 0;}
 CHECK(std::strcmp(argv[2],"retire")==0||std::strcmp(argv[2],"missing")==0||std::strcmp(argv[2],"forwarded")==0);
 FILE *file=nullptr;CHECK(fopen_s(&file,"symbol_runtime.fatbin","rb")==0&&file);CHECK(std::fseek(file,0,SEEK_END)==0);long n=std::ftell(file);CHECK(n>16&&n<=16777216);std::rewind(file);std::vector<unsigned char> image((size_t)n);CHECK(std::fread(image.data(),1,image.size(),file)==image.size());std::fclose(file);
 Wrapper wrapper={0x466243b1,1,image.data(),nullptr};void **token=p___cudaRegisterFatBinary(&wrapper);CHECK(token);
 char host;char name[]="ct_counter";p___cudaRegisterVar(token,&host,name,name,0,4,0,0);p___cudaRegisterFatBinaryEnd(token);CHECK(p_cudaGetLastError()==cudaSuccess);
 unsigned input=123,output=0;void *allocation=nullptr;CHECK(p_cudaMalloc(&allocation,4)==cudaSuccess);CHECK(p_cudaMemcpy(allocation,&input,4,cudaMemcpyHostToDevice)==cudaSuccess);CHECK(p_cudaMemcpy(&output,allocation,4,cudaMemcpyDeviceToHost)==cudaSuccess&&output==123);
 if(std::strcmp(argv[2],"retire")!=0) {
  CHECK(p_cudaGetSymbolAddress(&address,&host)==cudaErrorInsufficientDriver&&address==reinterpret_cast<void *>(uintptr_t(8192)));
  CHECK(p_cudaGetSymbolSize(&size,&host)==cudaErrorInsufficientDriver&&size==123);
  CHECK(p_cudaMemcpyToSymbol(&host,&input,4,0,cudaMemcpyHostToDevice)==cudaErrorInsufficientDriver);
  CHECK(p_cudaMemcpyFromSymbol(&output,&host,4,0,cudaMemcpyDeviceToHost)==cudaErrorInsufficientDriver&&output==123);
  p_cudaGetLastError();CHECK(p_cudaMemcpy(&output,allocation,4,cudaMemcpyDeviceToHost)==cudaSuccess&&output==123);CHECK(p_cudaFree(allocation)==cudaSuccess);
  p___cudaUnregisterFatBinary(token);std::printf("SYMBOL_NATIVE %s 26 35 123\n",argv[2]);return 0;
 }
 CHECK(p_cudaGetSymbolSize(&size,&host)==cudaSuccess&&size==4);CHECK(p_cudaGetSymbolAddress(&address,&host)==cudaSuccess&&address);
 CHECK(p_cudaMemcpyToSymbol(&host,&input,4,0,cudaMemcpyHostToDevice)==cudaSuccess);CHECK(p_cudaMemcpyFromSymbol(&output,&host,4,0,cudaMemcpyDeviceToHost)==cudaSuccess&&output==123);
 p___cudaUnregisterFatBinary(token);void *unchanged=address;
 CHECK(p_cudaGetSymbolAddress(&address,&host)==cudaErrorInvalidSymbol&&address==unchanged);
 CHECK(p_cudaGetSymbolSize(&size,&host)==cudaErrorInvalidSymbol&&size==4);
 CHECK(p_cudaMemcpyToSymbol(&host,nullptr,0,4,cudaMemcpyHostToDevice)==cudaErrorInvalidSymbol);
 CHECK(p_cudaMemcpyFromSymbol(nullptr,&host,0,4,cudaMemcpyDeviceToHost)==cudaErrorInvalidSymbol);
 p_cudaGetLastError();CHECK(p_cudaDeviceSynchronize()==cudaSuccess);
 CHECK(p_cudaMemcpy(&output,address,4,cudaMemcpyDeviceToHost)==cudaErrorInvalidValue&&output==123);p_cudaGetLastError();CHECK(p_cudaFree(allocation)==cudaSuccess);
 std::printf("SYMBOL_NATIVE retire 26 123 13 1\n");return 0;
}
