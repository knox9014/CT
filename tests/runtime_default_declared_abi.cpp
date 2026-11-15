#include "../include/ct_cudart.h"
#include <type_traits>
#include <cstdio>
static_assert(std::is_same_v<decltype(&__cudaRegisterVar),void(CT_RUNTIME_API *)(void **,char *,char *,const char *,int,size_t,int,int)>);
int main(){std::printf("DEFAULT_ABI 1 %zu\n",sizeof(size_t));return 0;}
