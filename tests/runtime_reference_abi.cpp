/* Official declarations are compiled independently from CT's declarations. */
#include <cuda_runtime_api.h>
#include <type_traits>
#include <cstdio>
#define CHECK(name, ...) static_assert(std::is_same_v<decltype(&name), __VA_ARGS__>)
CHECK(cudaGetDeviceCount,cudaError_t (CUDARTAPI *)(int *));
CHECK(cudaGetDevice,cudaError_t (CUDARTAPI *)(int *));
CHECK(cudaSetDevice,cudaError_t (CUDARTAPI *)(int));
CHECK(cudaDeviceSynchronize,cudaError_t (CUDARTAPI *)(void));
CHECK(cudaMalloc,cudaError_t (CUDARTAPI *)(void **,size_t));
CHECK(cudaFree,cudaError_t (CUDARTAPI *)(void *));
CHECK(cudaMemcpy,cudaError_t (CUDARTAPI *)(void *,const void *,size_t,cudaMemcpyKind));
CHECK(cudaMemset,cudaError_t (CUDARTAPI *)(void *,int,size_t));
CHECK(cudaGetLastError,cudaError_t (CUDARTAPI *)(void));
CHECK(cudaPeekAtLastError,cudaError_t (CUDARTAPI *)(void));
CHECK(cudaGetErrorName,const char * (CUDARTAPI *)(cudaError_t));
CHECK(cudaGetErrorString,const char * (CUDARTAPI *)(cudaError_t));
CHECK(cudaDriverGetVersion,cudaError_t (CUDARTAPI *)(int *));
CHECK(cudaRuntimeGetVersion,cudaError_t (CUDARTAPI *)(int *));
int main() {
    static_assert(sizeof(cudaError_t)==4 && sizeof(cudaMemcpyKind)==4 && sizeof(size_t)==8 && sizeof(void *)==8);
    std::printf("ABI 14 4 4 8 8\n%d %d %d %d %d\n%d %d %d %d %d %d %d %d %d %d %d %d\n",
        cudaMemcpyHostToHost,cudaMemcpyHostToDevice,cudaMemcpyDeviceToHost,cudaMemcpyDeviceToDevice,cudaMemcpyDefault,
        cudaSuccess,cudaErrorInvalidValue,cudaErrorMemoryAllocation,cudaErrorInitializationError,
        cudaErrorInvalidMemcpyDirection,cudaErrorInsufficientDriver,cudaErrorIncompatibleDriverContext,
        cudaErrorNoDevice,cudaErrorInvalidDevice,cudaErrorContextIsDestroyed,cudaErrorNotSupported,cudaErrorUnknown);
}
