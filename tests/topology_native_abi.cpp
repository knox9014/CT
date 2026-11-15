// Independent official-header Level Zero maximum topology and CUDA ABI control.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cuda.h>
#include <cuda_runtime_api.h>
#include <ze_api.h>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <climits>
#include <string>
#include <vector>
#define REQUIRE(x) do {if(!(x)){std::fprintf(stderr,"topology ABI line %d\n",__LINE__);return 42;}}while(0)
#define LOAD(m,n) auto p_##n=reinterpret_cast<decltype(&n)>(GetProcAddress(m,#n));REQUIRE(p_##n)
static_assert(CU_DEVICE_ATTRIBUTE_MULTIPROCESSOR_COUNT==16,"Driver topology enum");
static_assert(cudaDevAttrMultiProcessorCount==16,"Runtime topology enum");
struct Native {ze_driver_handle_t driver;ze_device_handle_t device;ze_device_properties_t properties;};
static int collect(HMODULE loader,std::vector<Native>& output) {
 LOAD(loader,zeInit);LOAD(loader,zeDriverGet);LOAD(loader,zeDeviceGet);LOAD(loader,zeDeviceGetProperties);
 REQUIRE(p_zeInit(ZE_INIT_FLAG_GPU_ONLY)==ZE_RESULT_SUCCESS);
 uint32_t count=0;REQUIRE(p_zeDriverGet(&count,nullptr)==ZE_RESULT_SUCCESS&&count>0&&count<=64);
 std::vector<ze_driver_handle_t> drivers(count);REQUIRE(p_zeDriverGet(&count,drivers.data())==ZE_RESULT_SUCCESS&&count<=drivers.size());
 for(uint32_t i=0;i<count;++i){
  uint32_t n=0;REQUIRE(p_zeDeviceGet(drivers[i],&n,nullptr)==ZE_RESULT_SUCCESS&&n<=64);
  if(!n)continue;
  std::vector<ze_device_handle_t> devices(n);REQUIRE(p_zeDeviceGet(drivers[i],&n,devices.data())==ZE_RESULT_SUCCESS&&n<=devices.size());
  for(uint32_t j=0;j<n;++j){
   ze_device_properties_t properties={};properties.stype=ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES;
   REQUIRE(p_zeDeviceGetProperties(devices[j],&properties)==ZE_RESULT_SUCCESS);
   if(properties.type==ZE_DEVICE_TYPE_GPU&&properties.vendorId==0x8086)output.push_back({drivers[i],devices[j],properties});
  }
 }
 return 0;
}
int main(int argc,char **argv){
 REQUIRE(argc==4);const char *mode=argv[3];
 const bool loader_case=std::strcmp(mode,"missing")==0||std::strcmp(mode,"forwarded")==0||std::strcmp(mode,"absent")==0;
 const bool virt=std::strncmp(mode,"virtual",7)==0||std::strcmp(mode,"minimal_virtual")==0||loader_case;
 const bool first=std::strstr(mode,"driver_first")!=nullptr;
 REQUIRE(SetEnvironmentVariableW(L"CT_VIRTUAL_TARGET",virt?L"ct-sm52-subset-v1":L"strict"));
 HMODULE runtime=LoadLibraryExA(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);REQUIRE(runtime);
 LOAD(runtime,cudaDeviceGetAttribute);LOAD(runtime,cudaGetDeviceCount);LOAD(runtime,cudaGetLastError);LOAD(runtime,cudaPeekAtLastError);
 struct Guard {int before,value,after;}out={123,456,789};
 REQUIRE(p_cudaDeviceGetAttribute(nullptr,static_cast<cudaDeviceAttr>(16),-1)==1);
 REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(16),-1)==101&&out.value==456);
 REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(9),0)==801&&out.value==456);
 REQUIRE(GetModuleHandleW(L"nvcuda.dll")==nullptr);
 if(loader_case){
  for(int i=0;i<3;++i){
   REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(16),0)==35&&out.value==456);
   REQUIRE(p_cudaGetLastError()==35&&out.before==123&&out.after==789);
  }
  std::puts("{\"status\":\"pass\",\"loader_error\":35}");return 0;
 }
 wchar_t system[MAX_PATH]={};UINT length=GetSystemDirectoryW(system,MAX_PATH);REQUIRE(length>0&&length<MAX_PATH);
 std::wstring path(system);path+=L"\\ze_loader.dll";
 HMODULE loader=LoadLibraryExW(path.c_str(),nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);REQUIRE(loader);
 std::vector<Native> before;REQUIRE(collect(loader,before)==0&&before.size()==1);
 const auto& raw=before[0].properties;
 REQUIRE(raw.numSlices>0&&raw.numSubslicesPerSlice>0);
 uint64_t product=uint64_t(raw.numSlices)*raw.numSubslicesPerSlice;REQUIRE(product<=INT_MAX);
 const int expected=static_cast<int>(product);
 if(first){HMODULE d=LoadLibraryExA(argv[2],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);REQUIRE(d);LOAD(d,cuInit);REQUIRE(p_cuInit(0)==CUDA_SUCCESS);}
 int count=0;REQUIRE(p_cudaGetDeviceCount(&count)==cudaSuccess&&count==1);
 HMODULE driver=GetModuleHandleW(L"nvcuda.dll");REQUIRE(driver);
 HMODULE identity=std::strncmp(mode,"minimal_",8)==0?GetModuleHandleW(L"ct_underlying.dll"):driver;REQUIRE(identity);
 LOAD(identity,cuDeviceGetName);char name[256]={};REQUIRE(p_cuDeviceGetName(name,256,0)==CUDA_SUCCESS);
 REQUIRE(std::memchr(raw.name,0,sizeof(raw.name))&&std::strcmp(name,raw.name)==0&&std::strncmp(name,"Intel",5)==0);
 for(const unsigned char *p=reinterpret_cast<const unsigned char *>(name);*p;++p)REQUIRE(*p>=32&&*p<127&&*p!='"'&&*p!='\\');
 LOAD(driver,cuDeviceGetAttribute);LOAD(driver,cuDeviceGet);LOAD(driver,cuCtxGetCurrent);
 CUdevice device=-1;REQUIRE(p_cuDeviceGet(&device,0)==CUDA_SUCCESS);
 CUcontext initial=reinterpret_cast<CUcontext>(uintptr_t(1));REQUIRE(p_cuCtxGetCurrent(&initial)==CUDA_SUCCESS&&initial==nullptr);
 int driver_code=-1,driver_value=-1,runtime_code=-1,runtime_value=-1;
 for(int repeat=0;repeat<3;++repeat){
  if(repeat==1)REQUIRE(SetEnvironmentVariableW(L"CT_VIRTUAL_TARGET",virt?L"strict":L"ct-sm52-subset-v1"));
  int value=456;driver_code=p_cuDeviceGetAttribute(&value,static_cast<CUdevice_attribute>(16),device);driver_value=value;
  REQUIRE(driver_code==(virt?CUDA_SUCCESS:CUDA_ERROR_NOT_SUPPORTED)&&value==(virt?expected:0));
  out.value=456;runtime_code=p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(16),0);runtime_value=out.value;
  REQUIRE(runtime_code==(virt?cudaSuccess:cudaErrorNotSupported)&&out.value==(virt?expected:456));
  REQUIRE(p_cudaPeekAtLastError()==801&&out.before==123&&out.after==789);
 }
 REQUIRE(p_cuDeviceGetAttribute(nullptr,static_cast<CUdevice_attribute>(16),0)==CUDA_ERROR_INVALID_VALUE);
 for(int ordinal:{-1,count}){
  out.value=456;REQUIRE(p_cuDeviceGetAttribute(&out.value,static_cast<CUdevice_attribute>(16),ordinal)==CUDA_ERROR_INVALID_DEVICE&&out.value==0);
  out.value=456;REQUIRE(p_cudaDeviceGetAttribute(&out.value,static_cast<cudaDeviceAttr>(16),ordinal)==101&&out.value==456);
 }
 REQUIRE(p_cudaGetLastError()==101&&out.before==123&&out.after==789);
 CUcontext final=reinterpret_cast<CUcontext>(uintptr_t(1));REQUIRE(p_cuCtxGetCurrent(&final)==CUDA_SUCCESS&&final==initial);
 std::vector<Native> after;REQUIRE(collect(loader,after)==0&&after.size()==1);
 REQUIRE(after[0].driver==before[0].driver&&after[0].device==before[0].device);
 REQUIRE(std::memcmp(after[0].properties.uuid.id,raw.uuid.id,sizeof(raw.uuid.id))==0);
 REQUIRE(after[0].properties.numSlices==raw.numSlices&&after[0].properties.numSubslicesPerSlice==raw.numSubslicesPerSlice);
 std::printf("{\"status\":\"pass\",\"virtual\":%s,\"device_name\":\"%s\",\"max_slices\":%u,\"max_subslices_per_slice\":%u,\"topology_count\":%d,\"driver_code\":%d,\"driver_value\":%d,\"runtime_code\":%d,\"runtime_value\":%d,\"identity_unique\":true,\"snapshot_stable\":true,\"context_unchanged\":true,\"policy_immutable\":true,\"physical_intel\":true,\"maxima_only\":true,\"nvidia_sm_claim\":false}\n",virt?"true":"false",name,raw.numSlices,raw.numSubslicesPerSlice,expected,driver_code,driver_value,runtime_code,runtime_value);
 return 0;
}
