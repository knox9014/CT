/* Original-header-only compile probe; no CT Runtime implementation claim. */
#include <cuda_runtime_api.h>
#include <type_traits>
#include <cstdio>
using Address=cudaError_t(CUDARTAPI *)(void **,const void *);
using Size=cudaError_t(CUDARTAPI *)(size_t *,const void *);
using To=cudaError_t(CUDARTAPI *)(const void *,const void *,size_t,size_t,cudaMemcpyKind);
using From=cudaError_t(CUDARTAPI *)(void *,const void *,size_t,size_t,cudaMemcpyKind);
static_assert(std::is_same_v<decltype(&cudaGetSymbolAddress),Address>);
static_assert(std::is_same_v<decltype(&cudaGetSymbolSize),Size>);
static_assert(std::is_same_v<decltype(&cudaMemcpyToSymbol),To>);
static_assert(std::is_same_v<decltype(&cudaMemcpyFromSymbol),From>);
static_assert(cudaErrorInvalidSymbol==13 && cudaErrorInvalidMemcpyDirection==21);
static_assert(cudaMemcpyHostToDevice==1 && cudaMemcpyDeviceToHost==2 && cudaMemcpyDeviceToDevice==3 && cudaMemcpyDefault==4);
int main(){std::printf("SYMBOL_ABI 4 %zu %zu %zu\n",sizeof(void *),sizeof(size_t),sizeof(cudaMemcpyKind));}
