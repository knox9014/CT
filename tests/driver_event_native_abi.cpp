// Official CUDA typedefs; actual CT Driver events and GPU copy checks.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cudaTypedefs.h>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#define REQUIRE(x) do { if(!(x)) { std::fprintf(stderr,"driver event line %d\n",__LINE__);return 42; } } while(0)
#define LOAD(name,version) auto p_##name=reinterpret_cast<PFN_##version>(GetProcAddress(driver,#name));REQUIRE(p_##name)
int main(int argc,char **argv) {
 REQUIRE(argc==3);
 HMODULE driver=LoadLibraryExA(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);REQUIRE(driver);
 auto base=reinterpret_cast<unsigned char *>(driver);auto dos=reinterpret_cast<IMAGE_DOS_HEADER *>(base);
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS64 *>(base+dos->e_lfanew);
 auto exports=reinterpret_cast<IMAGE_EXPORT_DIRECTORY *>(base+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress);
 REQUIRE(exports->NumberOfNames==47&&exports->NumberOfFunctions==47);
 LOAD(cuInit,cuInit_v2000);LOAD(cuDeviceGetCount,cuDeviceGetCount_v2000);LOAD(cuDeviceGetName,cuDeviceGetName_v2000);
 LOAD(cuCtxCreate_v2,cuCtxCreate_v3020);LOAD(cuCtxDestroy_v2,cuCtxDestroy_v4000);
 LOAD(cuCtxSetCurrent,cuCtxSetCurrent_v4000);LOAD(cuCtxGetCurrent,cuCtxGetCurrent_v4000);
 LOAD(cuMemAlloc_v2,cuMemAlloc_v3020);LOAD(cuMemFree_v2,cuMemFree_v3020);
 LOAD(cuMemcpyHtoD_v2,cuMemcpyHtoD_v3020);LOAD(cuMemcpyDtoH_v2,cuMemcpyDtoH_v3020);
 LOAD(cuEventCreate,cuEventCreate_v2000);LOAD(cuEventRecord,cuEventRecord_v2000);
 LOAD(cuEventSynchronize,cuEventSynchronize_v2000);LOAD(cuEventDestroy_v2,cuEventDestroy_v4000);
 LOAD(cuEventElapsedTime,cuEventElapsedTime_v2000);
 CUevent sentinel=reinterpret_cast<CUevent>(uintptr_t(0x8000)),a=sentinel,b=nullptr;
 REQUIRE(p_cuEventCreate(nullptr,0)==1);REQUIRE(p_cuEventCreate(&a,8)==1&&a==sentinel);
 REQUIRE(p_cuEventCreate(&a,0)==3&&a==sentinel);REQUIRE(p_cuInit(0)==0);
 int count=0,selected=-1;REQUIRE(p_cuDeviceGetCount(&count)==0);
 for(int i=0;i<count;++i) { char name[256]={};REQUIRE(p_cuDeviceGetName(name,256,i)==0);if(std::strstr(name,"B390"))selected=i; }
 REQUIRE(selected>=0);CUcontext context=nullptr;REQUIRE(p_cuCtxCreate_v2(&context,0,selected)==0&&context);
 for(unsigned f=1;f<8;++f)REQUIRE(p_cuEventCreate(&a,f)==801&&a==sentinel);
 REQUIRE(p_cuEventCreate(&a,0)==0&&a&&a!=sentinel);REQUIRE(p_cuEventCreate(&b,0)==0&&b&&a!=b);
 REQUIRE(p_cuEventSynchronize(a)==0);
 float ms=987.5f;REQUIRE(p_cuEventElapsedTime(&ms,a,b)==400&&ms==987.5f);
 REQUIRE(p_cuEventElapsedTime(nullptr,a,b)==1);REQUIRE(p_cuEventRecord(nullptr,nullptr)==400);
 REQUIRE(p_cuEventRecord(a,reinterpret_cast<CUstream>(uintptr_t(1)))==801);
 REQUIRE(p_cuEventElapsedTime(&ms,a,b)==400&&ms==987.5f);
 REQUIRE(p_cuEventRecord(a,nullptr)==0);
 CUdeviceptr device=0;REQUIRE(p_cuMemAlloc_v2(&device,4096)==0&&device);
 auto seed=static_cast<uint32_t>(std::strtoul(argv[2],nullptr,10));uint32_t input[1024],output[1024]={};
 for(uint32_t i=0;i<1024;++i)input[i]=(seed*7919u+i*1237u)^0xa5a55a5au;
 for(int i=0;i<8;++i) {
  REQUIRE(p_cuMemcpyHtoD_v2(device,input,sizeof(input))==0);
  REQUIRE(p_cuMemcpyDtoH_v2(output,device,sizeof(output))==0);
  REQUIRE(std::memcmp(input,output,sizeof(input))==0);
 }
 REQUIRE(p_cuEventRecord(b,nullptr)==0);REQUIRE(p_cuEventSynchronize(b)==0);
 CUresult timing=p_cuEventElapsedTime(&ms,a,b);
 if(timing!=0||!std::isfinite(ms)||ms<=0||ms>=60000) {
  std::fprintf(stderr,"EVENT_TIMING_REJECT code=%d milliseconds=%.9g\n",static_cast<int>(timing),static_cast<double>(ms));return 42;
 }
 float measured=ms;
 ms=987.5f;REQUIRE(p_cuEventElapsedTime(&ms,b,a)==1&&ms==987.5f);
 REQUIRE(p_cuEventElapsedTime(&ms,a,a)==0&&ms==0.0f);
 REQUIRE(p_cuEventRecord(a,nullptr)==0);ms=987.5f;REQUIRE(p_cuEventElapsedTime(&ms,a,b)==1&&ms==987.5f);
 REQUIRE(p_cuEventElapsedTime(&ms,b,a)==0&&std::isfinite(ms)&&ms>=0);
 CUcontext other=nullptr;REQUIRE(p_cuCtxCreate_v2(&other,0,selected)==0&&other!=context);
 REQUIRE(p_cuEventSynchronize(a)==400);REQUIRE(p_cuEventDestroy_v2(a)==400);
 CUevent retired=nullptr;REQUIRE(p_cuEventCreate(&retired,0)==0);REQUIRE(p_cuEventRecord(retired,nullptr)==0);
 REQUIRE(p_cuCtxDestroy_v2(other)==0);CUcontext current=nullptr;REQUIRE(p_cuCtxGetCurrent(&current)==0&&current==context);
 REQUIRE(p_cuEventSynchronize(retired)==400);REQUIRE(p_cuEventDestroy_v2(b)==0);REQUIRE(p_cuEventSynchronize(b)==400);
 REQUIRE(p_cuEventDestroy_v2(b)==400);REQUIRE(p_cuEventRecord(b,nullptr)==400);
 CUevent many[127]={};for(auto &e:many)REQUIRE(p_cuEventCreate(&e,0)==0&&e);
 CUevent excess=sentinel;REQUIRE(p_cuEventCreate(&excess,0)==2&&excess==sentinel);
 for(auto e:many)REQUIRE(p_cuEventDestroy_v2(e)==0);
 CUevent replacement=nullptr;REQUIRE(p_cuEventCreate(&replacement,0)==0&&replacement!=b&&replacement!=retired);
 REQUIRE(p_cuEventDestroy_v2(replacement)==0);REQUIRE(p_cuEventDestroy_v2(a)==0);
 REQUIRE(p_cuMemFree_v2(device)==0);REQUIRE(p_cuCtxDestroy_v2(context)==0);
 std::printf("{\"status\":\"pass\",\"seed\":%u,\"milliseconds\":%.9g,\"roundtrips\":8,\"words\":1024,\"ownership\":true,\"capacity\":128}\n",seed,static_cast<double>(measured));return 0;
}
