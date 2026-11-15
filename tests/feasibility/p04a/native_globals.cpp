#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <ze_api.h>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <vector>
#define CHECK(x) do{if(!(x)){std::fprintf(stderr,"probe assertion line %d\n",__LINE__);return 42;}}while(0)
#define LOAD(f) auto p_##f=reinterpret_cast<decltype(&f)>(GetProcAddress(loader,#f));CHECK(p_##f)
#define Z(f,...) do{auto code=p_##f(__VA_ARGS__);if(code!=ZE_RESULT_SUCCESS){std::fprintf(stderr,"native %s code=%08x\n",#f,(unsigned)code);return 42;}}while(0)
int main(){
 HMODULE loader=LoadLibraryExW(L"ze_loader.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);CHECK(loader);
 LOAD(zeInit);LOAD(zeDriverGet);LOAD(zeDeviceGet);LOAD(zeDeviceGetProperties);LOAD(zeDeviceGetCommandQueueGroupProperties);LOAD(zeContextCreate);LOAD(zeContextDestroy);LOAD(zeModuleCreate);LOAD(zeModuleDestroy);LOAD(zeModuleGetGlobalPointer);LOAD(zeKernelCreate);LOAD(zeKernelDestroy);LOAD(zeKernelSetGroupSize);LOAD(zeKernelSetArgumentValue);LOAD(zeCommandListCreateImmediate);LOAD(zeCommandListDestroy);LOAD(zeCommandListAppendLaunchKernel);LOAD(zeCommandListAppendMemoryCopy);LOAD(zeCommandListHostSynchronize);LOAD(zeMemAllocDevice);LOAD(zeMemFree);
 Z(zeInit,ZE_INIT_FLAG_GPU_ONLY);uint32_t n=0;Z(zeDriverGet,&n,nullptr);CHECK(n&&n<=64);std::vector<ze_driver_handle_t> drivers(n);Z(zeDriverGet,&n,drivers.data());
 ze_driver_handle_t driver=nullptr;ze_device_handle_t device=nullptr;
 for(auto d:drivers){uint32_t count=0;Z(zeDeviceGet,d,&count,nullptr);CHECK(count<=64);std::vector<ze_device_handle_t> devices(count);Z(zeDeviceGet,d,&count,devices.data());for(auto v:devices){ze_device_properties_t prop={};prop.stype=ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES;Z(zeDeviceGetProperties,v,&prop);if(prop.type==ZE_DEVICE_TYPE_GPU&&std::strstr(prop.name,"Arc")){driver=d;device=v;break;}}if(device)break;}CHECK(driver&&device);
 ze_context_desc_t cd={};cd.stype=ZE_STRUCTURE_TYPE_CONTEXT_DESC;ze_context_handle_t context=nullptr;Z(zeContextCreate,driver,&cd,&context);
 uint32_t count=0;Z(zeDeviceGetCommandQueueGroupProperties,device,&count,nullptr);CHECK(count&&count<=64);std::vector<ze_command_queue_group_properties_t> groups(count);for(auto &g:groups)g.stype=ZE_STRUCTURE_TYPE_COMMAND_QUEUE_GROUP_PROPERTIES;Z(zeDeviceGetCommandQueueGroupProperties,device,&count,groups.data());uint32_t ordinal=0;while(ordinal<count&&!(groups[ordinal].flags&ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COMPUTE))ordinal++;CHECK(ordinal<count);
 ze_command_queue_desc_t qd={};qd.stype=ZE_STRUCTURE_TYPE_COMMAND_QUEUE_DESC;qd.ordinal=ordinal;qd.mode=ZE_COMMAND_QUEUE_MODE_SYNCHRONOUS;qd.priority=ZE_COMMAND_QUEUE_PRIORITY_NORMAL;ze_command_list_handle_t list=nullptr;Z(zeCommandListCreateImmediate,context,device,&qd,&list);
 FILE *file=nullptr;CHECK(fopen_s(&file,"global.spv","rb")==0&&file);CHECK(std::fseek(file,0,SEEK_END)==0);long bytes=std::ftell(file);CHECK(bytes>0&&bytes<=65536);std::rewind(file);std::vector<unsigned char> spirv((size_t)bytes);CHECK(std::fread(spirv.data(),1,spirv.size(),file)==spirv.size());std::fclose(file);
 ze_module_desc_t md={};md.stype=ZE_STRUCTURE_TYPE_MODULE_DESC;md.format=ZE_MODULE_FORMAT_IL_SPIRV;md.inputSize=spirv.size();md.pInputModule=spirv.data();ze_module_handle_t module=nullptr,other=nullptr;Z(zeModuleCreate,context,device,&md,&module,nullptr);Z(zeModuleCreate,context,device,&md,&other,nullptr);
 size_t size=0,other_size=0;void *global=nullptr,*other_global=nullptr;Z(zeModuleGetGlobalPointer,module,"ct_global_probe",&size,&global);Z(zeModuleGetGlobalPointer,other,"ct_global_probe",&other_size,&other_global);CHECK(size==4&&other_size==4&&global&&other_global&&global!=other_global);
 ze_device_mem_alloc_desc_t ad={};ad.stype=ZE_STRUCTURE_TYPE_DEVICE_MEM_ALLOC_DESC;void *output=nullptr;Z(zeMemAllocDevice,context,&ad,4,4,device,&output);
 ze_kernel_desc_t kd={};kd.stype=ZE_STRUCTURE_TYPE_KERNEL_DESC;kd.pKernelName="ct_global_probe_kernel";ze_kernel_handle_t kernel=nullptr;Z(zeKernelCreate,module,&kd,&kernel);Z(zeKernelSetGroupSize,kernel,1,1,1);Z(zeKernelSetArgumentValue,kernel,0,sizeof(output),&output);ze_group_count_t gc={1,1,1};unsigned values[3]={};
 for(unsigned i=0;i<3;i++){if(i==2){unsigned replacement=123;Z(zeCommandListAppendMemoryCopy,list,global,&replacement,4,nullptr,0,nullptr);}Z(zeCommandListAppendLaunchKernel,list,kernel,&gc,nullptr,0,nullptr);Z(zeCommandListAppendMemoryCopy,list,&values[i],output,4,nullptr,0,nullptr);Z(zeCommandListHostSynchronize,list,10000000000ULL);}
 unsigned current=0,other_value=0;Z(zeCommandListAppendMemoryCopy,list,&current,global,4,nullptr,0,nullptr);Z(zeCommandListAppendMemoryCopy,list,&other_value,other_global,4,nullptr,0,nullptr);Z(zeCommandListHostSynchronize,list,10000000000ULL);CHECK(values[0]==7&&values[1]==8&&values[2]==123&&current==124&&other_value==7);
 Z(zeKernelDestroy,kernel);Z(zeModuleDestroy,module);unsigned preserved=0;Z(zeCommandListAppendMemoryCopy,list,&preserved,other_global,4,nullptr,0,nullptr);Z(zeCommandListHostSynchronize,list,10000000000ULL);CHECK(preserved==7);
 Z(zeModuleDestroy,other);Z(zeMemFree,context,output);Z(zeCommandListDestroy,list);Z(zeContextDestroy,context);std::puts("{\"scope\":\"native feasibility only\",\"reads\":[7,8,123],\"stored\":124,\"other_module\":7,\"preserved_after_unload\":7}");return 0;
}
