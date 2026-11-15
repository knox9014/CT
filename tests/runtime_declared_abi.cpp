#include "../include/ct_cudart.h"
#include <type_traits>
#include <cstdio>
#define CHECK(name, ...) static_assert(std::is_same_v<decltype(&name), __VA_ARGS__>)
CHECK(cudaGetDeviceCount,int (CT_RUNTIME_API *)(int *));
CHECK(cudaGetDevice,int (CT_RUNTIME_API *)(int *));
CHECK(cudaSetDevice,int (CT_RUNTIME_API *)(int));
CHECK(cudaDeviceSynchronize,int (CT_RUNTIME_API *)(void));
CHECK(cudaMalloc,int (CT_RUNTIME_API *)(void **,size_t));
CHECK(cudaFree,int (CT_RUNTIME_API *)(void *));
CHECK(cudaMemcpy,int (CT_RUNTIME_API *)(void *,const void *,size_t,int));
CHECK(cudaMemset,int (CT_RUNTIME_API *)(void *,int,size_t));
CHECK(cudaGetLastError,int (CT_RUNTIME_API *)(void));
CHECK(cudaPeekAtLastError,int (CT_RUNTIME_API *)(void));
CHECK(cudaGetErrorName,const char * (CT_RUNTIME_API *)(int));
CHECK(cudaGetErrorString,const char * (CT_RUNTIME_API *)(int));
CHECK(cudaDriverGetVersion,int (CT_RUNTIME_API *)(int *));
CHECK(cudaRuntimeGetVersion,int (CT_RUNTIME_API *)(int *));
CHECK(cudaEventCreate,int (CT_RUNTIME_API *)(CT_cudaEvent_t *));
CHECK(cudaEventRecord,int (CT_RUNTIME_API *)(CT_cudaEvent_t,CT_cudaStream_t));
CHECK(cudaEventSynchronize,int (CT_RUNTIME_API *)(CT_cudaEvent_t));
CHECK(cudaEventDestroy,int (CT_RUNTIME_API *)(CT_cudaEvent_t));
CHECK(cudaEventElapsedTime,int (CT_RUNTIME_API *)(float *,CT_cudaEvent_t,CT_cudaEvent_t));
int main() {
    static_assert(sizeof(int)==4 && sizeof(size_t)==8 && sizeof(void *)==8);
    std::printf("ABI 14 4 4 8 8\n0 1 2 3 4\n0 1 2 3 21 35 49 100 101 709 801 999\n");
}
