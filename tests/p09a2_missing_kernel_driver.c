/* CT-owned ABI control; implements memory/bootstrap only, no GPU execution. */
#include <windows.h>
#include <stdint.h>
static __declspec(thread) uintptr_t current;
#define API __declspec(dllexport) int __stdcall
API cuInit(unsigned flags) {(void)flags;return 0;}
API cuDeviceGetCount(int *out) {*out=1;return 0;}
API cuDeviceGet(int *out,int ordinal) {*out=ordinal;return ordinal?101:0;}
API cuCtxGetCurrent(uintptr_t *out) {*out=current;return 0;}
API cuCtxGetDevice(int *out) {*out=0;return 0;}
API cuCtxSetCurrent(uintptr_t context) {current=context;return 0;}
API cuDevicePrimaryCtxRetain(uintptr_t *out,int device) {(void)device;*out=77;return 0;}
API cuDevicePrimaryCtxRelease_v2(int device) {(void)device;return 0;}
API cuCtxSynchronize(void) {return 0;}
API cuMemAlloc_v2(uint64_t *out,size_t size) {(void)size;*out=4096;return 0;}
API cuMemFree_v2(uint64_t pointer) {(void)pointer;return 0;}
API cuMemcpyHtoD_v2(uint64_t dst,const void *src,size_t size) {(void)dst;(void)src;(void)size;return 0;}
API cuMemcpyDtoH_v2(void *dst,uint64_t src,size_t size) {(void)dst;(void)src;(void)size;return 0;}
API cuMemcpyDtoD_v2(uint64_t dst,uint64_t src,size_t size) {(void)dst;(void)src;(void)size;return 0;}
API cuMemsetD8_v2(uint64_t dst,unsigned char value,size_t size) {(void)dst;(void)value;(void)size;return 0;}
