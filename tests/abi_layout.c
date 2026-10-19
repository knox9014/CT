/* Development-only layout oracle. Compile against official Level Zero v1.27.0. */
#include <stdio.h>
#include <stddef.h>
#include "ze_api.h"
#define START(n,t) printf("%s %zu %zu [",n,sizeof(t),(size_t)__alignof(t))
#define F(t,f) printf("%zu, ",offsetof(t,f))
#define LAST(t,f) printf("%zu]\n",offsetof(t,f))
int main(void) {
    START("DriverProperties",ze_driver_properties_t);
    F(ze_driver_properties_t,stype); F(ze_driver_properties_t,pNext);
    F(ze_driver_properties_t,uuid); LAST(ze_driver_properties_t,driverVersion);
    START("DeviceProperties",ze_device_properties_t);
    F(ze_device_properties_t,stype); F(ze_device_properties_t,pNext);
    F(ze_device_properties_t,type); F(ze_device_properties_t,vendorId);
    F(ze_device_properties_t,deviceId); F(ze_device_properties_t,flags);
    F(ze_device_properties_t,subdeviceId); F(ze_device_properties_t,coreClockRate);
    F(ze_device_properties_t,maxMemAllocSize); F(ze_device_properties_t,maxHardwareContexts);
    F(ze_device_properties_t,maxCommandQueuePriority); F(ze_device_properties_t,numThreadsPerEU);
    F(ze_device_properties_t,physicalEUSimdWidth); F(ze_device_properties_t,numEUsPerSubslice);
    F(ze_device_properties_t,numSubslicesPerSlice); F(ze_device_properties_t,numSlices);
    F(ze_device_properties_t,timerResolution); F(ze_device_properties_t,timestampValidBits);
    F(ze_device_properties_t,kernelTimestampValidBits); F(ze_device_properties_t,uuid);
    LAST(ze_device_properties_t,name);
    START("ComputeProperties",ze_device_compute_properties_t);
    F(ze_device_compute_properties_t,stype); F(ze_device_compute_properties_t,pNext);
    F(ze_device_compute_properties_t,maxTotalGroupSize); F(ze_device_compute_properties_t,maxGroupSizeX);
    F(ze_device_compute_properties_t,maxGroupSizeY); F(ze_device_compute_properties_t,maxGroupSizeZ);
    F(ze_device_compute_properties_t,maxGroupCountX); F(ze_device_compute_properties_t,maxGroupCountY);
    F(ze_device_compute_properties_t,maxGroupCountZ); F(ze_device_compute_properties_t,maxSharedLocalMemory);
    F(ze_device_compute_properties_t,numSubGroupSizes); LAST(ze_device_compute_properties_t,subGroupSizes);
    START("QueueGroupProperties",ze_command_queue_group_properties_t);
    F(ze_command_queue_group_properties_t,stype); F(ze_command_queue_group_properties_t,pNext);
    F(ze_command_queue_group_properties_t,flags); F(ze_command_queue_group_properties_t,maxMemoryFillPatternSize);
    LAST(ze_command_queue_group_properties_t,numQueues);
    START("ContextDesc",ze_context_desc_t);
    F(ze_context_desc_t,stype); F(ze_context_desc_t,pNext); LAST(ze_context_desc_t,flags);
    START("QueueDesc",ze_command_queue_desc_t);
    F(ze_command_queue_desc_t,stype); F(ze_command_queue_desc_t,pNext);
    F(ze_command_queue_desc_t,ordinal); F(ze_command_queue_desc_t,index);
    F(ze_command_queue_desc_t,flags); F(ze_command_queue_desc_t,mode); LAST(ze_command_queue_desc_t,priority);
    START("ListDesc",ze_command_list_desc_t);
    F(ze_command_list_desc_t,stype); F(ze_command_list_desc_t,pNext);
    F(ze_command_list_desc_t,commandQueueGroupOrdinal); LAST(ze_command_list_desc_t,flags);
    START("DeviceAllocDesc",ze_device_mem_alloc_desc_t);
    F(ze_device_mem_alloc_desc_t,stype); F(ze_device_mem_alloc_desc_t,pNext);
    F(ze_device_mem_alloc_desc_t,flags); LAST(ze_device_mem_alloc_desc_t,ordinal);
    START("HostAllocDesc",ze_host_mem_alloc_desc_t);
    F(ze_host_mem_alloc_desc_t,stype); F(ze_host_mem_alloc_desc_t,pNext); LAST(ze_host_mem_alloc_desc_t,flags);
    START("ModuleDesc",ze_module_desc_t);
    F(ze_module_desc_t,stype); F(ze_module_desc_t,pNext); F(ze_module_desc_t,format);
    F(ze_module_desc_t,inputSize); F(ze_module_desc_t,pInputModule);
    F(ze_module_desc_t,pBuildFlags); LAST(ze_module_desc_t,pConstants);
    START("KernelDesc",ze_kernel_desc_t);
    F(ze_kernel_desc_t,stype); F(ze_kernel_desc_t,pNext);
    F(ze_kernel_desc_t,flags); LAST(ze_kernel_desc_t,pKernelName);
    START("GroupCount",ze_group_count_t);
    F(ze_group_count_t,groupCountX); F(ze_group_count_t,groupCountY); LAST(ze_group_count_t,groupCountZ);
    return 0;
}
