/* Experimental x64 CUDA Driver ABI subset. No CUDA version conformance claim. */
#ifndef CT_CUDA_H
#define CT_CUDA_H
#include <stddef.h>
#if defined(_WIN32)
#define CT_CUDA_API __stdcall
#else
#define CT_CUDA_API
#endif
typedef int CUresult;
typedef int CUdevice;
typedef struct CTcontext *CUcontext;
typedef unsigned long long CUdeviceptr;
typedef struct CTmodule *CUmodule;
typedef struct CTfunction *CUfunction;
typedef struct CTstream *CUstream;
#define CT_DRIVER_FUNCTIONS(X) \
 X(cuInit, (unsigned int flags)) \
 X(cuDriverGetVersion, (int *version)) \
 X(cuDeviceGetCount, (int *count)) \
 X(cuDeviceGet, (CUdevice *device, int ordinal)) \
 X(cuDeviceGetName, (char *name, int length, CUdevice device)) \
 X(cuDeviceGetAttribute, (int *value, int attribute, CUdevice device)) \
 X(cuDevicePrimaryCtxRetain, (CUcontext *context, CUdevice device)) \
 X(cuDevicePrimaryCtxSetFlags_v2, (CUdevice device, unsigned int flags)) \
 X(cuCtxGetFlags, (unsigned int *flags)) \
 X(cuDevicePrimaryCtxReset_v2, (CUdevice device)) \
 X(cuDevicePrimaryCtxGetState, (CUdevice device, unsigned int *flags, int *active)) \
 X(cuDevicePrimaryCtxRelease_v2, (CUdevice device)) \
 X(cuCtxCreate_v2, (CUcontext *context, unsigned int flags, CUdevice device)) \
 X(cuCtxDestroy_v2, (CUcontext context)) \
 X(cuCtxGetCurrent, (CUcontext *context)) \
 X(cuCtxSetCurrent, (CUcontext context)) \
 X(cuCtxPushCurrent_v2, (CUcontext context)) \
 X(cuCtxPopCurrent_v2, (CUcontext *context)) \
 X(cuCtxGetDevice, (CUdevice *device)) \
 X(cuCtxSynchronize, (void)) \
 X(cuMemAlloc_v2, (CUdeviceptr *pointer, size_t bytes)) \
 X(cuMemFree_v2, (CUdeviceptr pointer)) \
 X(cuMemcpyHtoD_v2, (CUdeviceptr destination, const void *source, size_t bytes)) \
 X(cuMemcpyDtoH_v2, (void *destination, CUdeviceptr source, size_t bytes)) \
 X(cuMemcpyDtoD_v2, (CUdeviceptr destination, CUdeviceptr source, size_t bytes)) \
 X(cuMemsetD8_v2, (CUdeviceptr destination, unsigned char value, size_t count)) \
 X(cuMemsetD16_v2, (CUdeviceptr destination, unsigned short value, size_t count)) \
 X(cuMemsetD32_v2, (CUdeviceptr destination, unsigned int value, size_t count)) \
 X(cuGetErrorName, (CUresult code, const char **name)) \
 X(cuGetErrorString, (CUresult code, const char **message)) \
 X(cuModuleLoadData, (CUmodule *module, const void *image)) \
 X(cuModuleGetFunction, (CUfunction *function, CUmodule module, const char *name)) \
 X(cuModuleUnload, (CUmodule module)) \
 X(cuLaunchKernel, (CUfunction function, unsigned int gx, unsigned int gy, unsigned int gz, unsigned int bx, unsigned int by, unsigned int bz, unsigned int shared, CUstream stream, void **arguments, void **extra)) \
 X(cuGetProcAddress, (const char *symbol, void **function, int version, unsigned long long flags)) \
 X(cuGetProcAddress_v2, (const char *symbol, void **function, int version, unsigned long long flags, int *status))
#ifdef __cplusplus
extern "C" {
#endif
#define CT_DECLARE(name,args) typedef CUresult (CT_CUDA_API *PFN_##name) args; CUresult CT_CUDA_API name args;
CT_DRIVER_FUNCTIONS(CT_DECLARE)
#undef CT_DECLARE
#ifdef __cplusplus
}
#endif
#endif
