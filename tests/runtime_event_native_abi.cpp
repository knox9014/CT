// Official CUDA ABI; optional event bridge and real Runtime/Driver integration.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cuda_runtime_api.h>
#include <cuda.h>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstring>
#define REQUIRE(x) do{if(!(x)){std::fprintf(stderr,"runtime event line %d\n",__LINE__);return 42;}}while(0)
#define LOAD(module,name) auto p_##name=reinterpret_cast<decltype(&name)>(GetProcAddress(module,#name));REQUIRE(p_##name)
int main(int argc,char **argv) {
 REQUIRE(argc==3);HMODULE rt=LoadLibraryExA(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);REQUIRE(rt);
 auto base=reinterpret_cast<unsigned char *>(rt);auto dos=reinterpret_cast<IMAGE_DOS_HEADER *>(base);auto nt=reinterpret_cast<IMAGE_NT_HEADERS64 *>(base+dos->e_lfanew);
 auto exports=reinterpret_cast<IMAGE_EXPORT_DIRECTORY *>(base+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress);REQUIRE(exports->NumberOfNames==40&&exports->NumberOfFunctions==40);
 LOAD(rt,cudaEventCreate);LOAD(rt,cudaEventRecord);LOAD(rt,cudaEventSynchronize);LOAD(rt,cudaEventDestroy);LOAD(rt,cudaEventElapsedTime);
 LOAD(rt,cudaGetLastError);LOAD(rt,cudaGetErrorName);LOAD(rt,cudaMalloc);LOAD(rt,cudaFree);LOAD(rt,cudaHostAlloc);LOAD(rt,cudaFreeHost);LOAD(rt,cudaMemcpyAsync);LOAD(rt,cudaDeviceSynchronize);
 REQUIRE(std::strcmp(p_cudaGetErrorName(cudaErrorNotReady),"cudaErrorNotReady")==0);
 cudaEvent_t invalid=reinterpret_cast<cudaEvent_t>(uintptr_t(1));float ms=987.5f;
 REQUIRE(p_cudaEventCreate(nullptr)==1);REQUIRE(p_cudaEventRecord(nullptr,nullptr)==400);REQUIRE(p_cudaEventSynchronize(invalid)==400);REQUIRE(p_cudaEventDestroy(invalid)==400);
 REQUIRE(p_cudaEventElapsedTime(&ms,nullptr,nullptr)==400&&ms==987.5f);REQUIRE(p_cudaEventElapsedTime(nullptr,nullptr,nullptr)==1);
 REQUIRE(GetModuleHandleW(L"nvcuda.dll")==nullptr);p_cudaGetLastError();
 cudaEvent_t a=invalid,b=nullptr;
 if(std::strcmp(argv[2],"positive")!=0) {
  REQUIRE(p_cudaEventCreate(&a)==35&&a==invalid);REQUIRE(p_cudaEventCreate(&a)==35&&a==invalid);REQUIRE(p_cudaGetLastError()==35);
  if(std::strcmp(argv[2],"absent")==0) {
   REQUIRE(GetModuleHandleW(L"nvcuda.dll")==nullptr);
   std::puts("{\"status\":\"pass\",\"error\":35}");return 0;
  }
  HMODULE d=GetModuleHandleW(L"nvcuda.dll");REQUIRE(d);
  const char *names[]={"cuEventCreate","cuEventRecord","cuEventSynchronize","cuEventDestroy_v2","cuEventElapsedTime"};
  if(std::strncmp(argv[2],"missing_",8)==0) {
   REQUIRE(std::strlen(argv[2])==9);int missing=argv[2][8]-'0';REQUIRE(missing>=0&&missing<5);
   for(int i=0;i<5;++i)REQUIRE((GetProcAddress(d,names[i])==nullptr)==(i==missing));
  } else {
   REQUIRE(std::strcmp(argv[2],"forwarded")==0);auto forwarded=GetProcAddress(d,names[0]);REQUIRE(forwarded);
   HMODULE foreign=GetModuleHandleW(L"event_foreign.dll");REQUIRE(foreign);REQUIRE(forwarded==GetProcAddress(foreign,"event_foreign"));
   for(int i=1;i<5;++i)REQUIRE(GetProcAddress(d,names[i]));
  }
  void *core=nullptr;REQUIRE(p_cudaMalloc(&core,64)==0&&core);REQUIRE(p_cudaDeviceSynchronize()==0);REQUIRE(p_cudaFree(core)==0);
  REQUIRE(p_cudaEventCreate(&a)==35&&a==invalid);
  std::puts("{\"status\":\"pass\",\"error\":35,\"core_alive\":true,\"extension_verified\":true}");return 0;
 }
 REQUIRE(p_cudaEventCreate(&a)==0&&a!=invalid);REQUIRE(p_cudaEventCreate(&b)==0&&b!=a);
 REQUIRE(p_cudaEventSynchronize(a)==0);REQUIRE(p_cudaEventElapsedTime(&ms,a,b)==400&&ms==987.5f);p_cudaGetLastError();
 void *device=nullptr,*host=nullptr;REQUIRE(p_cudaMalloc(&device,4096)==0);REQUIRE(p_cudaHostAlloc(&host,4096,0)==0);
 auto words=static_cast<unsigned *>(host);for(unsigned i=0;i<1024;++i)words[i]=i*13+7;
 REQUIRE(p_cudaEventRecord(a,nullptr)==0);REQUIRE(p_cudaMemcpyAsync(device,host,4096,cudaMemcpyHostToDevice,nullptr)==0);
 REQUIRE(p_cudaEventRecord(b,nullptr)==0);REQUIRE(p_cudaEventSynchronize(b)==0);
 REQUIRE(p_cudaEventElapsedTime(&ms,a,b)==0&&std::isfinite(ms)&&ms>0);float measured=ms;
 REQUIRE(p_cudaEventElapsedTime(&ms,a,a)==0&&ms==0);ms=987.5f;REQUIRE(p_cudaEventElapsedTime(&ms,b,a)==1&&ms==987.5f);p_cudaGetLastError();
 HMODULE driver=GetModuleHandleW(L"nvcuda.dll");REQUIRE(driver);LOAD(driver,cuCtxGetCurrent);LOAD(driver,cuCtxGetDevice);LOAD(driver,cuCtxCreate_v2);LOAD(driver,cuCtxDestroy_v2);
 CUcontext before=nullptr;CUdevice ordinal=0;REQUIRE(p_cuCtxGetCurrent(&before)==0&&before);REQUIRE(p_cuCtxGetDevice(&ordinal)==0);
 CUcontext other=nullptr;REQUIRE(p_cuCtxCreate_v2(&other,0,ordinal)==0);
 REQUIRE(p_cudaEventSynchronize(a)==400);REQUIRE(p_cudaEventDestroy(a)==400);REQUIRE(p_cuCtxDestroy_v2(other)==0);p_cudaGetLastError();
 REQUIRE(p_cudaEventRecord(a,nullptr)==0);REQUIRE(p_cudaDeviceSynchronize()==0);REQUIRE(p_cudaEventElapsedTime(&ms,b,a)==0&&std::isfinite(ms)&&ms>=0);
 REQUIRE(p_cudaEventDestroy(a)==0);REQUIRE(p_cudaEventSynchronize(a)==400);REQUIRE(p_cudaEventDestroy(a)==400);p_cudaGetLastError();
 REQUIRE(p_cudaEventDestroy(b)==0);REQUIRE(p_cudaFree(device)==0);REQUIRE(p_cudaFreeHost(host)==0);
 CUcontext after=nullptr;REQUIRE(p_cuCtxGetCurrent(&after)==0&&after==before);
 std::printf("{\"status\":\"pass\",\"milliseconds\":%.9g,\"context_preserved\":true}\n",static_cast<double>(measured));return 0;
}
