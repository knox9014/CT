#include <cuda_profiler_api.h>
#include <type_traits>
#include <cstdio>
static_assert(std::is_same_v<decltype(&cudaProfilerStart),cudaError_t (CUDARTAPI *)(void)>);
static_assert(std::is_same_v<decltype(&cudaProfilerStop),cudaError_t (CUDARTAPI *)(void)>);
int main() {static_assert(sizeof(cudaError_t)==4&&sizeof(void *)==8);std::puts("PROFILER_ABI 2 4 8");}
