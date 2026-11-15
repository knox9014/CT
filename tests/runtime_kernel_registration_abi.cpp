/* Compile the original registration header once, without nvcc's host injection. */
#include <cuda_runtime_api.h>
#include <math.h>
#include <string.h>
#define __CUDA_INTERNAL_COMPILATION__
#define __CUDA_INCLUDE_COMPILER_INTERNAL_HEADERS__
#include <crt/host_runtime.h>
#include <type_traits>
#include <cstdio>
#define CHECK(name, ...) static_assert(std::is_same_v<decltype(&name), __VA_ARGS__>)
CHECK(__cudaRegisterFatBinary,void ** (CUDARTAPI *)(void *));
CHECK(__cudaRegisterFatBinaryEnd,void (CUDARTAPI *)(void **));
CHECK(__cudaUnregisterFatBinary,void (CUDARTAPI *)(void **));
CHECK(__cudaRegisterFunction,void (CUDARTAPI *)(void **,const char *,char *,const char *,int,uint3 *,uint3 *,dim3 *,dim3 *,int *));
CHECK(__cudaPopCallConfiguration,cudaError_t (CUDARTAPI *)(dim3 *,dim3 *,size_t *,void *));
/* nvcc emits an empty constructor even for a type-only TU. These local shims
   only let the declaration probe link; runtime_kernel_native_abi exercises the
   actual Rust callbacks separately. No GPU/runtime result is inferred here. */
extern "C" void ** CUDARTAPI __cudaRegisterFatBinary(void *) { return nullptr; }
extern "C" void CUDARTAPI __cudaRegisterFatBinaryEnd(void **) {}
extern "C" void CUDARTAPI __cudaUnregisterFatBinary(void **) {}
extern int kernel_launch_reference();
int main() {
    std::printf("KERNEL_ABI 7 %zu %zu %zu %zu\n%d %d %d %d\n",sizeof(dim3),alignof(dim3),sizeof(size_t),sizeof(cudaStream_t),
                cudaErrorInvalidConfiguration,cudaErrorInvalidDeviceFunction,cudaErrorInvalidPtx,cudaErrorInvalidResourceHandle);
    return kernel_launch_reference();
}
