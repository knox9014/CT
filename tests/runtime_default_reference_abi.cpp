#include <cuda_runtime_api.h>
#include <math.h>
#include <string.h>
#define __CUDA_INTERNAL_COMPILATION__
#define __CUDA_INCLUDE_COMPILER_INTERNAL_HEADERS__
#include <crt/host_runtime.h>
#include <type_traits>
#include <cstdio>
static_assert(std::is_same_v<decltype(&__cudaRegisterVar),void(CUDARTAPI *)(void **,char *,char *,const char *,int,size_t,int,int)>);
int main(){std::printf("DEFAULT_ABI 1 %zu\n",sizeof(size_t));return 0;}
