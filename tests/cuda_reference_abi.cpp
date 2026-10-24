// Official-header-only translation unit; no CT CUDA declarations here.
#include <cudaTypedefs.h>
#include "cuda_abi_probe.hpp"

int main() {
    std::puts("ABI:windows-x64");
#define PROBE(name, version) abi_function(#name, static_cast<PFN_##version>(nullptr))
    PROBE(cuInit, cuInit_v2000);
    PROBE(cuDriverGetVersion, cuDriverGetVersion_v2020);
    PROBE(cuDeviceGetCount, cuDeviceGetCount_v2000);
    PROBE(cuDeviceGet, cuDeviceGet_v2000);
    PROBE(cuDeviceGetName, cuDeviceGetName_v2000);
    PROBE(cuDeviceGetAttribute, cuDeviceGetAttribute_v2000);
    PROBE(cuDevicePrimaryCtxRetain, cuDevicePrimaryCtxRetain_v7000);
    PROBE(cuDevicePrimaryCtxSetFlags_v2, cuDevicePrimaryCtxSetFlags_v11000);
    PROBE(cuCtxGetFlags, cuCtxGetFlags_v7000);
    PROBE(cuDevicePrimaryCtxReset_v2, cuDevicePrimaryCtxReset_v11000);
    PROBE(cuDevicePrimaryCtxGetState, cuDevicePrimaryCtxGetState_v7000);
    PROBE(cuDevicePrimaryCtxRelease_v2, cuDevicePrimaryCtxRelease_v11000);
    PROBE(cuCtxCreate_v2, cuCtxCreate_v3020);
    PROBE(cuCtxDestroy_v2, cuCtxDestroy_v4000);
    PROBE(cuCtxGetCurrent, cuCtxGetCurrent_v4000);
    PROBE(cuCtxSetCurrent, cuCtxSetCurrent_v4000);
    PROBE(cuCtxPushCurrent_v2, cuCtxPushCurrent_v4000);
    PROBE(cuCtxPopCurrent_v2, cuCtxPopCurrent_v4000);
    PROBE(cuCtxGetDevice, cuCtxGetDevice_v2000);
    PROBE(cuCtxSynchronize, cuCtxSynchronize_v2000);
    PROBE(cuMemAlloc_v2, cuMemAlloc_v3020);
    PROBE(cuMemFree_v2, cuMemFree_v3020);
    PROBE(cuMemGetAddressRange_v2, cuMemGetAddressRange_v3020);
    PROBE(cuPointerGetAttribute, cuPointerGetAttribute_v4000);
    PROBE(cuMemcpyHtoD_v2, cuMemcpyHtoD_v3020);
    PROBE(cuMemcpyDtoH_v2, cuMemcpyDtoH_v3020);
    PROBE(cuMemcpyDtoD_v2, cuMemcpyDtoD_v3020);
    PROBE(cuMemsetD8_v2, cuMemsetD8_v3020);
    PROBE(cuMemsetD16_v2, cuMemsetD16_v3020);
    PROBE(cuMemsetD32_v2, cuMemsetD32_v3020);
    PROBE(cuGetErrorName, cuGetErrorName_v6000);
    PROBE(cuGetErrorString, cuGetErrorString_v6000);
    PROBE(cuModuleLoadData, cuModuleLoadData_v2000);
    PROBE(cuModuleGetGlobal_v2, cuModuleGetGlobal_v3020);
    PROBE(cuModuleGetFunction, cuModuleGetFunction_v2000);
    PROBE(cuModuleUnload, cuModuleUnload_v2000);
    PROBE(cuLaunchKernel, cuLaunchKernel_v4000);
    PROBE(cuGetProcAddress, cuGetProcAddress_v11030);
    PROBE(cuGetProcAddress_v2, cuGetProcAddress_v12000);
#undef PROBE
    std::printf("enums:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d\n",
        CUDA_SUCCESS, CUDA_ERROR_INVALID_VALUE, CUDA_ERROR_OUT_OF_MEMORY,
        CUDA_ERROR_NOT_INITIALIZED, CUDA_ERROR_NO_DEVICE, CUDA_ERROR_INVALID_DEVICE,
        CUDA_ERROR_INVALID_CONTEXT, CUDA_ERROR_INVALID_PTX, CUDA_ERROR_INVALID_HANDLE,
        CUDA_ERROR_NOT_FOUND, CUDA_ERROR_NOT_SUPPORTED, CUDA_ERROR_UNKNOWN);
    std::printf("query:%d:%d:%d\n", CU_GET_PROC_ADDRESS_SUCCESS,
        CU_GET_PROC_ADDRESS_SYMBOL_NOT_FOUND, CU_GET_PROC_ADDRESS_VERSION_NOT_SUFFICIENT);
    std::printf("primary-errors:%d\n", CUDA_ERROR_CONTEXT_IS_DESTROYED);
    std::printf("flags:%u:%u:%u:%u:%u:%u:%u:%u\n", CU_CTX_SCHED_AUTO,
        CU_CTX_SCHED_SPIN, CU_CTX_SCHED_YIELD, CU_CTX_SCHED_BLOCKING_SYNC,
        CU_CTX_SCHED_MASK, CU_CTX_MAP_HOST, CU_CTX_LMEM_RESIZE_TO_MAX, CU_CTX_FLAGS_MASK);
    std::printf("pointer-attributes:%d:%d:%d:%d:%d:%d:%d:%d\n", CU_POINTER_ATTRIBUTE_CONTEXT, CU_POINTER_ATTRIBUTE_MEMORY_TYPE, CU_POINTER_ATTRIBUTE_IS_MANAGED, CU_POINTER_ATTRIBUTE_DEVICE_ORDINAL, CU_POINTER_ATTRIBUTE_RANGE_START_ADDR, CU_POINTER_ATTRIBUTE_RANGE_SIZE, CU_POINTER_ATTRIBUTE_MAPPING_SIZE, CU_POINTER_ATTRIBUTE_MEMORY_BLOCK_ID);
    std::printf("attributes:%d:%d:%d:%d:%d:%d:%d:%d:%d\n",
        CU_DEVICE_ATTRIBUTE_MAX_THREADS_PER_BLOCK, CU_DEVICE_ATTRIBUTE_MAX_BLOCK_DIM_X,
        CU_DEVICE_ATTRIBUTE_MAX_BLOCK_DIM_Y, CU_DEVICE_ATTRIBUTE_MAX_BLOCK_DIM_Z,
        CU_DEVICE_ATTRIBUTE_MAX_GRID_DIM_X, CU_DEVICE_ATTRIBUTE_MAX_GRID_DIM_Y,
        CU_DEVICE_ATTRIBUTE_MAX_GRID_DIM_Z, CU_DEVICE_ATTRIBUTE_COMPUTE_MODE,
        CU_COMPUTEMODE_DEFAULT);
}
