/* Original vendor declarations, independent from CT's header. */
#include <cuda_runtime.h>
#include <type_traits>
#include <cstdio>
#define CHECK(name, ...) static_assert(std::is_same_v<decltype(&name), __VA_ARGS__>)
CHECK(__cudaPushCallConfiguration,unsigned (CUDARTAPI *)(dim3,dim3,size_t,cudaStream_t));
using LaunchSignature=cudaError_t (CUDARTAPI *)(const void *,dim3,dim3,void **,size_t,cudaStream_t);
static_assert(std::is_same_v<decltype(static_cast<LaunchSignature>(&cudaLaunchKernel)),LaunchSignature>);
int kernel_launch_reference() {
    static_assert(sizeof(dim3)==12 && alignof(dim3)==4 && sizeof(uint3)==12);
    return 0;
}
