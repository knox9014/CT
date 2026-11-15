// Official CUDA query ABI plus late Runtime registration; no NVIDIA library linked.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cuda.h>
#include <cuda_runtime_api.h>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <vector>
#define REQUIRE(x) do {if(!(x)){std::fprintf(stderr,"virtual target ABI line %d\n",__LINE__);return 42;}}while(0)
#define LOAD(m,n) auto p_##n=reinterpret_cast<decltype(&n)>(GetProcAddress(m,#n));REQUIRE(p_##n)
static std::vector<unsigned char> image(const char *text) {
 size_t size=std::strlen(text)+1,payload=(size+7)&~size_t(7);
 std::vector<unsigned char> b(88+payload,0);
 auto u32=[&](size_t at,uint32_t v){std::memcpy(b.data()+at,&v,4);};
 auto u64=[&](size_t at,uint64_t v){std::memcpy(b.data()+at,&v,8);};
 u32(0,0xba55ed50);b[4]=1;b[6]=16;u64(8,72+payload);
 b[16]=1;b[18]=1;b[19]=1;u32(20,72);u64(24,payload);
 u32(36,64);u32(40,8u<<16);u32(44,52);u32(56,0x41);
 std::memcpy(b.data()+88,text,size);return b;
}
static unsigned exports(HMODULE module) {
 auto b=reinterpret_cast<unsigned char *>(module);auto dos=reinterpret_cast<IMAGE_DOS_HEADER *>(b);
 auto nt=reinterpret_cast<IMAGE_NT_HEADERS64 *>(b+dos->e_lfanew);
 auto e=reinterpret_cast<IMAGE_EXPORT_DIRECTORY *>(b+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress);
 return e->NumberOfFunctions==e->NumberOfNames?e->NumberOfNames:0;
}
int main(int argc,char **argv) {
 REQUIRE(argc==4);const char *mode=argv[3];
 const bool loader=std::strcmp(mode,"loader")==0;
 const bool invalid=std::strcmp(mode,"invalid")==0 || std::strcmp(mode,"empty")==0 || std::strcmp(mode,"nonunicode")==0;
 const bool flags=std::strcmp(mode,"flags")==0;
 const bool virt=std::strncmp(mode,"virtual",7)==0 || flags;
 const bool driver_first=std::strstr(mode,"driver_first")!=nullptr || invalid || flags;
 REQUIRE(SetEnvironmentVariableW(L"CT_VIRTUAL_TARGET",virt||loader?L"ct-sm52-subset-v1":L"strict"));
 if(invalid||flags)REQUIRE(SetEnvironmentVariableW(L"CT_VIRTUAL_TARGET",L"typo"));
 if(std::strcmp(mode,"empty")==0)REQUIRE(SetEnvironmentVariableW(L"CT_VIRTUAL_TARGET",L""));
 if(std::strcmp(mode,"nonunicode")==0){wchar_t bad[]={0xd800,0};REQUIRE(SetEnvironmentVariableW(L"CT_VIRTUAL_TARGET",bad));}
 HMODULE runtime=LoadLibraryExA(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);REQUIRE(runtime&&exports(runtime)==40);
 LOAD(runtime,cudaDeviceGetAttribute);LOAD(runtime,cudaGetLastError);LOAD(runtime,cudaPeekAtLastError);LOAD(runtime,cudaGetDeviceCount);
 struct Guard{int before,value,after;}out={123,456,789};
 REQUIRE(p_cudaDeviceGetAttribute(nullptr,static_cast<cudaDeviceAttr>(75),-1)==1);
 REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(75),-1)==101);
 REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(9),0)==801);p_cudaGetLastError();
 if(loader){
  for(int i=0;i<3;i++)REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(75),0)==35&&out.value==456);
  REQUIRE(out.before==123&&out.after==789);std::puts("{\"status\":\"pass\",\"loader_error\":35}");return 0;
 }
 HMODULE driver=nullptr;
 if(driver_first){driver=LoadLibraryExA(argv[2],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);REQUIRE(driver);}
 if(driver_first){
  LOAD(driver,cuInit);LOAD(driver,cuDeviceGetAttribute);
  REQUIRE(p_cuDeviceGetAttribute(&out.value,CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MAJOR,0)==CUDA_ERROR_NOT_INITIALIZED&&out.value==456);
  if(flags){REQUIRE(p_cuInit(1)==CUDA_ERROR_INVALID_VALUE);REQUIRE(SetEnvironmentVariableW(L"CT_VIRTUAL_TARGET",L"ct-sm52-subset-v1"));}
  if(invalid){
   REQUIRE(p_cuInit(0)==CUDA_ERROR_INVALID_VALUE);REQUIRE(SetEnvironmentVariableW(L"CT_VIRTUAL_TARGET",L"ct-sm52-subset-v1"));
   REQUIRE(p_cuInit(0)==CUDA_ERROR_INVALID_VALUE);
   REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(75),0)==1&&out.value==456);
   REQUIRE(out.before==123&&out.after==789);std::puts("{\"status\":\"pass\",\"invalid_config\":1}");return 0;
  }
  REQUIRE(p_cuInit(0)==CUDA_SUCCESS);
  REQUIRE(SetEnvironmentVariableW(L"CT_VIRTUAL_TARGET",virt?L"strict":L"ct-sm52-subset-v1"));
 }else{
  int count=0;REQUIRE(p_cudaGetDeviceCount(&count)==cudaSuccess&&count>0);
  REQUIRE(SetEnvironmentVariableW(L"CT_VIRTUAL_TARGET",virt?L"strict":L"ct-sm52-subset-v1"));
  driver=GetModuleHandleW(L"nvcuda.dll");REQUIRE(driver);
 }
 REQUIRE(exports(driver)==47);
 LOAD(driver,cuInit);LOAD(driver,cuDeviceGet);LOAD(driver,cuDeviceGetName);LOAD(driver,cuDeviceGetAttribute);LOAD(driver,cuCtxGetCurrent);
 LOAD(runtime,cudaDriverGetVersion);LOAD(runtime,cudaRuntimeGetVersion);
 CUcontext before=reinterpret_cast<CUcontext>(uintptr_t(1));REQUIRE(p_cuCtxGetCurrent(&before)==CUDA_SUCCESS&&before==nullptr);
 CUdevice device=-1;REQUIRE(p_cuDeviceGet(&device,0)==CUDA_SUCCESS);
 char name[256]={};REQUIRE(p_cuDeviceGetName(name,sizeof(name),device)==CUDA_SUCCESS&&std::strstr(name,"Intel")!=nullptr);
 int shared=-1;REQUIRE(p_cudaDeviceGetAttribute(&shared,cudaDevAttrMaxSharedMemoryPerBlock,0)==cudaSuccess&&shared>=0&&shared<=16384);
 REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(9),0)==801);
 for(int repeat=0;repeat<3;repeat++)for(int a:{75,76}){
  int value=456;auto code=p_cuDeviceGetAttribute(&value,static_cast<CUdevice_attribute>(a),device);
  REQUIRE(code==(virt?CUDA_SUCCESS:CUDA_ERROR_NOT_SUPPORTED));REQUIRE(value==(virt?(a==75?5:2):0));
  out.value=456;auto runtime_code=p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(a),0);
  REQUIRE(runtime_code==(virt?cudaSuccess:cudaErrorNotSupported));REQUIRE(out.value==(virt?(a==75?5:2):456));
  REQUIRE(out.before==123&&out.after==789&&p_cudaPeekAtLastError()==801);
 }
 int count=0;REQUIRE(p_cudaGetDeviceCount(&count)==cudaSuccess&&count>0);out.value=456;
 REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(75),count)==101&&out.value==456);
 int version=123;REQUIRE(p_cudaDriverGetVersion(&version)==801&&version==0);version=123;REQUIRE(p_cudaRuntimeGetVersion(&version)==801&&version==0);
 {int value=456;REQUIRE(p_cuDeviceGetAttribute(&value,static_cast<CUdevice_attribute>(13),device)==CUDA_ERROR_NOT_SUPPORTED&&value==0);}
 {int value=456;auto code=p_cuDeviceGetAttribute(&value,static_cast<CUdevice_attribute>(16),device);
  REQUIRE(code==(virt?CUDA_SUCCESS:CUDA_ERROR_NOT_SUPPORTED));REQUIRE(virt?value>0:value==0);
  out.value=456;auto runtime_code=p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(16),0);
  REQUIRE(runtime_code==(virt?cudaSuccess:cudaErrorNotSupported));REQUIRE(out.value==(virt?value:456));}
 CUcontext after=reinterpret_cast<CUcontext>(uintptr_t(1));REQUIRE(p_cuCtxGetCurrent(&after)==CUDA_SUCCESS&&after==before);
 // Register unsupported code AFTER successful virtual queries. It must never run.
 if(virt){
  using Reg=void ** (__stdcall *)(void *);using End=void (__stdcall *)(void **);
  using Func=void (__stdcall *)(void **,const char *,char *,const char *,int,void *,void *,void *,void *,void *);
  auto reg=reinterpret_cast<Reg>(GetProcAddress(runtime,"__cudaRegisterFatBinary"));
  auto end=reinterpret_cast<End>(GetProcAddress(runtime,"__cudaRegisterFatBinaryEnd"));
  auto func=reinterpret_cast<Func>(GetProcAddress(runtime,"__cudaRegisterFunction"));
  auto unreg=reinterpret_cast<End>(GetProcAddress(runtime,"__cudaUnregisterFatBinary"));REQUIRE(reg&&end&&func&&unreg);
  LOAD(runtime,cudaLaunchKernel);LOAD(runtime,cudaDeviceSynchronize);
  auto data=image(".version 8.0 .target sm_52 .address_size 64 .entry late(){bar.sync 1;ret;}");
  struct Wrapper{unsigned magic,version;void *data,*extra;}wrapper={0x466243b1,1,data.data(),nullptr};
  static int marker;char symbol[]="late";void **token=reg(&wrapper);REQUIRE(token);p_cudaGetLastError();
  func(token,reinterpret_cast<const char *>(&marker),symbol,symbol,-1,nullptr,nullptr,nullptr,nullptr,nullptr);end(token);REQUIRE(p_cudaGetLastError()==0);
  REQUIRE(p_cudaLaunchKernel(&marker,dim3(1),dim3(1),nullptr,0,nullptr)==801);REQUIRE(p_cudaGetLastError()==801);
  unreg(token);REQUIRE(p_cudaDeviceSynchronize()==cudaSuccess);
 }
 REQUIRE(p_cuInit(0)==CUDA_SUCCESS);
 std::printf("{\"status\":\"pass\",\"virtual\":%s,\"major\":%d,\"minor\":%d,\"context_unchanged\":true,\"physical_intel\":true,\"policy_immutable\":true,\"late_unsupported_rejected\":%s}",virt?"true":"false",virt?5:0,virt?2:0,virt?"true":"false");
 return 0;
}
