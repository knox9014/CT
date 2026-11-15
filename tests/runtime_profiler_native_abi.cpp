// Official Runtime/profiler types, no NVIDIA implementation linked.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cuda_runtime_api.h>
#include <cuda_profiler_api.h>
#include <cuda.h>
#include <cstdio>
#include <cstring>
#include <cstdint>
#define REQUIRE(x) do{if(!(x)){std::fprintf(stderr,"profiler ABI line %d\n",__LINE__);return 42;}}while(0)
#define LOAD(m,n) auto p_##n=reinterpret_cast<decltype(&n)>(GetProcAddress(m,#n));REQUIRE(p_##n)
int main(int argc,char **argv) {
 REQUIRE(argc==3);HMODULE rt=LoadLibraryExA(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);REQUIRE(rt);
 auto base=reinterpret_cast<unsigned char *>(rt);auto dos=reinterpret_cast<IMAGE_DOS_HEADER *>(base);auto nt=reinterpret_cast<IMAGE_NT_HEADERS64 *>(base+dos->e_lfanew);
 auto exports=reinterpret_cast<IMAGE_EXPORT_DIRECTORY *>(base+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress);REQUIRE(exports->NumberOfNames==40&&exports->NumberOfFunctions==40);
 LOAD(rt,cudaProfilerStart);LOAD(rt,cudaProfilerStop);LOAD(rt,cudaGetLastError);LOAD(rt,cudaPeekAtLastError);
 LOAD(rt,cudaMalloc);LOAD(rt,cudaFree);LOAD(rt,cudaHostAlloc);LOAD(rt,cudaFreeHost);LOAD(rt,cudaMemcpyAsync);LOAD(rt,cudaDeviceSynchronize);
 REQUIRE(p_cudaMalloc(nullptr,1)==1);REQUIRE(p_cudaPeekAtLastError()==1);
 if(std::strcmp(argv[2],"absent")==0) {
  REQUIRE(p_cudaProfilerStop()==35);REQUIRE(p_cudaProfilerStart()==35);REQUIRE(p_cudaProfilerStart()==35);REQUIRE(p_cudaGetLastError()==35);
  REQUIRE(GetModuleHandleW(L"nvcuda.dll")==nullptr);std::puts("{\"status\":\"pass\",\"mode\":\"absent\",\"error\":35}");return 0;
 }
 REQUIRE(p_cudaProfilerStop()==0);REQUIRE(p_cudaProfilerStop()==0);REQUIRE(p_cudaProfilerStart()==0);REQUIRE(p_cudaProfilerStart()==0);REQUIRE(p_cudaProfilerStop()==0);
 REQUIRE(p_cudaPeekAtLastError()==1);REQUIRE(p_cudaGetLastError()==1);REQUIRE(p_cudaGetLastError()==0);
 HMODULE driver=GetModuleHandleW(L"nvcuda.dll");REQUIRE(driver);LOAD(driver,cuCtxGetCurrent);
 CUcontext before=nullptr;REQUIRE(p_cuCtxGetCurrent(&before)==0&&before);int error=0;
 if(std::strcmp(argv[2],"queued_error")==0) {
  void *device=nullptr,*host=nullptr;REQUIRE(p_cudaMalloc(&device,64)==0);REQUIRE(p_cudaHostAlloc(&host,64,0)==0);
  auto invalid=reinterpret_cast<void *>(reinterpret_cast<uintptr_t>(device)+64);
  REQUIRE(p_cudaMemcpyAsync(invalid,host,4,cudaMemcpyHostToDevice,nullptr)==0);REQUIRE(p_cudaDeviceSynchronize()==1);
  REQUIRE(p_cudaProfilerStart()==1);REQUIRE(p_cudaProfilerStop()==1);REQUIRE(p_cudaProfilerStop()==1);REQUIRE(p_cudaGetLastError()==1);
  REQUIRE(p_cudaFree(device)==1);REQUIRE(p_cudaFreeHost(host)==1);error=1;
 } else if(std::strcmp(argv[2],"trap_sync")==0) {
  // Prove the native sync trap is active after successful profiler calls.
  REQUIRE(p_cudaDeviceSynchronize()==1);REQUIRE(p_cudaGetLastError()==1);error=1;
 } else {REQUIRE(std::strcmp(argv[2],"positive")==0);REQUIRE(p_cudaDeviceSynchronize()==0);}
 CUcontext after=nullptr;REQUIRE(p_cuCtxGetCurrent(&after)==0&&after==before);
 std::printf("{\"status\":\"pass\",\"mode\":\"%s\",\"error\":%d,\"context_preserved\":true,\"control_verified\":true}\n",argv[2],error);return 0;
}
