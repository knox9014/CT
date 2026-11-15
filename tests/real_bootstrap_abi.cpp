#include "bootstrap_resolver_abi.cpp"
using ModuleLoad = CUresult (CUDAAPI *)(CUmodule *, const void *);
using Launch = CUresult (CUDAAPI *)(CUfunction, unsigned, unsigned, unsigned, unsigned, unsigned, unsigned,
                                  unsigned, CUstream, void **, void **);
static_assert(std::is_same_v<PFN_cuModuleLoadData_v2000, ModuleLoad>);
static_assert(std::is_same_v<PFN_cuLaunchKernel_v4000, Launch>);
