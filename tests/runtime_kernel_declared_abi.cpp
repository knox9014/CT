#include "../include/ct_cudart.h"
#include <type_traits>
#include <cstdio>
#define CHECK(name, ...) static_assert(std::is_same_v<decltype(&name), __VA_ARGS__>)
CHECK(__cudaRegisterFatBinary,void ** (CT_RUNTIME_API *)(void *));
CHECK(__cudaRegisterFatBinaryEnd,void (CT_RUNTIME_API *)(void **));
CHECK(__cudaUnregisterFatBinary,void (CT_RUNTIME_API *)(void **));
CHECK(__cudaRegisterFunction,void (CT_RUNTIME_API *)(void **,const char *,char *,const char *,int,CT_uint3 *,CT_uint3 *,CT_dim3 *,CT_dim3 *,int *));
CHECK(__cudaPushCallConfiguration,unsigned (CT_RUNTIME_API *)(CT_dim3,CT_dim3,size_t,CT_cudaStream_t));
CHECK(__cudaPopCallConfiguration,int (CT_RUNTIME_API *)(CT_dim3 *,CT_dim3 *,size_t *,void *));
CHECK(cudaLaunchKernel,int (CT_RUNTIME_API *)(const void *,CT_dim3,CT_dim3,void **,size_t,CT_cudaStream_t));
int main() {
    static_assert(sizeof(CT_dim3)==12 && alignof(CT_dim3)==4 && sizeof(CT_uint3)==12);
    std::printf("KERNEL_ABI 7 %zu %zu %zu %zu\n9 98 218 400\n",sizeof(CT_dim3),alignof(CT_dim3),sizeof(size_t),sizeof(CT_cudaStream_t));
}
