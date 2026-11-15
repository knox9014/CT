#include "../include/ct_cudart.h"
#include <type_traits>
#include <cstdio>
static_assert(std::is_same_v<decltype(&cudaProfilerStart),int (CT_RUNTIME_API *)(void)>);
static_assert(std::is_same_v<decltype(&cudaProfilerStop),int (CT_RUNTIME_API *)(void)>);
int main() {static_assert(sizeof(int)==4&&sizeof(void *)==8);std::puts("PROFILER_ABI 2 4 8");}
