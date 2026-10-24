/* Negative-control forwarding provider; no nominal CT code is compiled with test macros. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "../include/ct_cuda.h"
static INIT_ONCE once=INIT_ONCE_STATIC_INIT;
static HMODULE underlying;
static BOOL CALLBACK load(PINIT_ONCE i,PVOID p,PVOID *c) { (void)i;(void)p;(void)c; underlying=LoadLibraryW(L"ct_underlying.dll"); return underlying!=NULL; }
static FARPROC resolve(const char *name) { if(!InitOnceExecuteOnce(&once,load,NULL,NULL))return NULL; return GetProcAddress(underlying,name); }
CUresult CT_CUDA_API cuInit(unsigned int flags) {
    PFN_cuInit ct_proc=(PFN_cuInit)resolve("cuInit"); return ct_proc?ct_proc(flags):999;
}
CUresult CT_CUDA_API cuDriverGetVersion(int *version) {
    PFN_cuDriverGetVersion ct_proc=(PFN_cuDriverGetVersion)resolve("cuDriverGetVersion"); return ct_proc?ct_proc(version):999;
}
CUresult CT_CUDA_API cuDeviceGetCount(int *count) {
    PFN_cuDeviceGetCount ct_proc=(PFN_cuDeviceGetCount)resolve("cuDeviceGetCount"); return ct_proc?ct_proc(count):999;
}
CUresult CT_CUDA_API cuDeviceGet(CUdevice *device, int ordinal) {
    PFN_cuDeviceGet ct_proc=(PFN_cuDeviceGet)resolve("cuDeviceGet"); return ct_proc?ct_proc(device,ordinal):999;
}
CUresult CT_CUDA_API cuDeviceGetName(char *name, int length, CUdevice device) {
    PFN_cuDeviceGetName ct_proc=(PFN_cuDeviceGetName)resolve("cuDeviceGetName"); return ct_proc?ct_proc(name,length,device):999;
}
CUresult CT_CUDA_API cuDeviceGetAttribute(int *value, int attribute, CUdevice device) {
    PFN_cuDeviceGetAttribute ct_proc=(PFN_cuDeviceGetAttribute)resolve("cuDeviceGetAttribute"); return ct_proc?ct_proc(value,attribute,device):999;
}
CUresult CT_CUDA_API cuDevicePrimaryCtxRetain(CUcontext *context, CUdevice device) {
    PFN_cuDevicePrimaryCtxRetain ct_proc=(PFN_cuDevicePrimaryCtxRetain)resolve("cuDevicePrimaryCtxRetain"); return ct_proc?ct_proc(context,device):999;
}
CUresult CT_CUDA_API cuDevicePrimaryCtxSetFlags_v2(CUdevice device, unsigned int flags) {
    PFN_cuDevicePrimaryCtxSetFlags_v2 ct_proc=(PFN_cuDevicePrimaryCtxSetFlags_v2)resolve("cuDevicePrimaryCtxSetFlags_v2"); return ct_proc?ct_proc(device,flags):999;
}
CUresult CT_CUDA_API cuCtxGetFlags(unsigned int *flags) {
    PFN_cuCtxGetFlags ct_proc=(PFN_cuCtxGetFlags)resolve("cuCtxGetFlags"); return ct_proc?ct_proc(flags):999;
}
CUresult CT_CUDA_API cuDevicePrimaryCtxReset_v2(CUdevice device) {
    PFN_cuDevicePrimaryCtxReset_v2 ct_proc=(PFN_cuDevicePrimaryCtxReset_v2)resolve("cuDevicePrimaryCtxReset_v2"); return ct_proc?ct_proc(device):999;
}
CUresult CT_CUDA_API cuDevicePrimaryCtxGetState(CUdevice device, unsigned int *flags, int *active) {
    PFN_cuDevicePrimaryCtxGetState ct_proc=(PFN_cuDevicePrimaryCtxGetState)resolve("cuDevicePrimaryCtxGetState"); return ct_proc?ct_proc(device,flags,active):999;
}
CUresult CT_CUDA_API cuDevicePrimaryCtxRelease_v2(CUdevice device) {
    PFN_cuDevicePrimaryCtxRelease_v2 ct_proc=(PFN_cuDevicePrimaryCtxRelease_v2)resolve("cuDevicePrimaryCtxRelease_v2"); return ct_proc?ct_proc(device):999;
}
CUresult CT_CUDA_API cuCtxCreate_v2(CUcontext *context, unsigned int flags, CUdevice device) {
    PFN_cuCtxCreate_v2 ct_proc=(PFN_cuCtxCreate_v2)resolve("cuCtxCreate_v2"); return ct_proc?ct_proc(context,flags,device):999;
}
CUresult CT_CUDA_API cuCtxDestroy_v2(CUcontext context) {
    PFN_cuCtxDestroy_v2 ct_proc=(PFN_cuCtxDestroy_v2)resolve("cuCtxDestroy_v2"); return ct_proc?ct_proc(context):999;
}
CUresult CT_CUDA_API cuCtxGetCurrent(CUcontext *context) {
    PFN_cuCtxGetCurrent ct_proc=(PFN_cuCtxGetCurrent)resolve("cuCtxGetCurrent"); return ct_proc?ct_proc(context):999;
}
CUresult CT_CUDA_API cuCtxSetCurrent(CUcontext context) {
    PFN_cuCtxSetCurrent ct_proc=(PFN_cuCtxSetCurrent)resolve("cuCtxSetCurrent"); return ct_proc?ct_proc(context):999;
}
CUresult CT_CUDA_API cuCtxPushCurrent_v2(CUcontext context) {
    PFN_cuCtxPushCurrent_v2 ct_proc=(PFN_cuCtxPushCurrent_v2)resolve("cuCtxPushCurrent_v2"); return ct_proc?ct_proc(context):999;
}
CUresult CT_CUDA_API cuCtxPopCurrent_v2(CUcontext *context) {
    PFN_cuCtxPopCurrent_v2 ct_proc=(PFN_cuCtxPopCurrent_v2)resolve("cuCtxPopCurrent_v2"); return ct_proc?ct_proc(context):999;
}
CUresult CT_CUDA_API cuCtxGetDevice(CUdevice *device) {
    PFN_cuCtxGetDevice ct_proc=(PFN_cuCtxGetDevice)resolve("cuCtxGetDevice"); return ct_proc?ct_proc(device):999;
}
CUresult CT_CUDA_API cuCtxSynchronize(void) {
    PFN_cuCtxSynchronize ct_proc=(PFN_cuCtxSynchronize)resolve("cuCtxSynchronize"); return ct_proc?ct_proc():999;
}
CUresult CT_CUDA_API cuMemAlloc_v2(CUdeviceptr *pointer, size_t bytes) {
    PFN_cuMemAlloc_v2 ct_proc=(PFN_cuMemAlloc_v2)resolve("cuMemAlloc_v2"); return ct_proc?ct_proc(pointer,bytes):999;
}
CUresult CT_CUDA_API cuMemFree_v2(CUdeviceptr pointer) {
    PFN_cuMemFree_v2 ct_proc=(PFN_cuMemFree_v2)resolve("cuMemFree_v2"); return ct_proc?ct_proc(pointer):999;
}
CUresult CT_CUDA_API cuMemGetAddressRange_v2(CUdeviceptr *base, size_t *size, CUdeviceptr pointer) {
    PFN_cuMemGetAddressRange_v2 ct_proc=(PFN_cuMemGetAddressRange_v2)resolve("cuMemGetAddressRange_v2"); return ct_proc?ct_proc(base,size,pointer):999;
}
CUresult CT_CUDA_API cuPointerGetAttribute(void *data, int attribute, CUdeviceptr pointer) {
    PFN_cuPointerGetAttribute ct_proc=(PFN_cuPointerGetAttribute)resolve("cuPointerGetAttribute"); return ct_proc?ct_proc(data,attribute,pointer):999;
}
CUresult CT_CUDA_API cuMemcpyHtoD_v2(CUdeviceptr destination, const void *source, size_t bytes) {
#if defined(NOOP_COPY)
    (void)destination;(void)source;(void)bytes;return 0;
#else
    PFN_cuMemcpyHtoD_v2 ct_proc=(PFN_cuMemcpyHtoD_v2)resolve("cuMemcpyHtoD_v2"); return ct_proc?ct_proc(destination,source,bytes):999;
#endif
}
CUresult CT_CUDA_API cuMemcpyDtoH_v2(void *destination, CUdeviceptr source, size_t bytes) {
    PFN_cuMemcpyDtoH_v2 ct_proc=(PFN_cuMemcpyDtoH_v2)resolve("cuMemcpyDtoH_v2"); return ct_proc?ct_proc(destination,source,bytes):999;
}
CUresult CT_CUDA_API cuMemcpyDtoD_v2(CUdeviceptr destination, CUdeviceptr source, size_t bytes) {
    PFN_cuMemcpyDtoD_v2 ct_proc=(PFN_cuMemcpyDtoD_v2)resolve("cuMemcpyDtoD_v2"); return ct_proc?ct_proc(destination,source,bytes):999;
}
CUresult CT_CUDA_API cuMemsetD8_v2(CUdeviceptr destination, unsigned char value, size_t count) {
#if defined(NOOP_FILL)
    if(value==0x34) return 0;
#endif
    PFN_cuMemsetD8_v2 ct_proc=(PFN_cuMemsetD8_v2)resolve("cuMemsetD8_v2"); return ct_proc?ct_proc(destination,value,count):999;
}
CUresult CT_CUDA_API cuMemsetD16_v2(CUdeviceptr destination, unsigned short value, size_t count) {
    PFN_cuMemsetD16_v2 ct_proc=(PFN_cuMemsetD16_v2)resolve("cuMemsetD16_v2"); return ct_proc?ct_proc(destination,value,count):999;
}
CUresult CT_CUDA_API cuMemsetD32_v2(CUdeviceptr destination, unsigned int value, size_t count) {
    PFN_cuMemsetD32_v2 ct_proc=(PFN_cuMemsetD32_v2)resolve("cuMemsetD32_v2"); return ct_proc?ct_proc(destination,value,count):999;
}
CUresult CT_CUDA_API cuGetErrorName(CUresult code, const char **name) {
    PFN_cuGetErrorName ct_proc=(PFN_cuGetErrorName)resolve("cuGetErrorName"); return ct_proc?ct_proc(code,name):999;
}
CUresult CT_CUDA_API cuGetErrorString(CUresult code, const char **message) {
    PFN_cuGetErrorString ct_proc=(PFN_cuGetErrorString)resolve("cuGetErrorString"); return ct_proc?ct_proc(code,message):999;
}
CUresult CT_CUDA_API cuModuleLoadData(CUmodule *module, const void *image) {
    PFN_cuModuleLoadData ct_proc=(PFN_cuModuleLoadData)resolve("cuModuleLoadData"); return ct_proc?ct_proc(module,image):999;
}
CUresult CT_CUDA_API cuModuleGetFunction(CUfunction *function, CUmodule module, const char *name) {
    PFN_cuModuleGetFunction ct_proc=(PFN_cuModuleGetFunction)resolve("cuModuleGetFunction"); return ct_proc?ct_proc(function,module,name):999;
}
CUresult CT_CUDA_API cuModuleUnload(CUmodule module) {
    PFN_cuModuleUnload ct_proc=(PFN_cuModuleUnload)resolve("cuModuleUnload"); return ct_proc?ct_proc(module):999;
}
CUresult CT_CUDA_API cuLaunchKernel(CUfunction function, unsigned int gx, unsigned int gy, unsigned int gz, unsigned int bx, unsigned int by, unsigned int bz, unsigned int shared, CUstream stream, void **arguments, void **extra) {
#ifdef NOOP_LAUNCH
    (void)function;(void)gx;(void)gy;(void)gz;(void)bx;(void)by;(void)bz;(void)shared;(void)stream;(void)arguments;(void)extra;return 0;
#else
    PFN_cuLaunchKernel ct_proc=(PFN_cuLaunchKernel)resolve("cuLaunchKernel"); return ct_proc?ct_proc(function,gx,gy,gz,bx,by,bz,shared,stream,arguments,extra):999;
#endif
}
CUresult CT_CUDA_API cuGetProcAddress(const char *symbol, void **function, int version, unsigned long long flags) {
    PFN_cuGetProcAddress ct_proc=(PFN_cuGetProcAddress)resolve("cuGetProcAddress"); return ct_proc?ct_proc(symbol,function,version,flags):999;
}
CUresult CT_CUDA_API cuGetProcAddress_v2(const char *symbol, void **function, int version, unsigned long long flags, int *status) {
    PFN_cuGetProcAddress_v2 ct_proc=(PFN_cuGetProcAddress_v2)resolve("cuGetProcAddress_v2"); return ct_proc?ct_proc(symbol,function,version,flags,status):999;
}
