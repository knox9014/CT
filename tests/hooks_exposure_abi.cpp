// Compile-only public DeviceGet signature; private tables remain reference-derived.
#include "bootstrap_resolver_abi.cpp"
using DeviceGet = CUresult (CUDAAPI *)(CUdevice *, int);
static_assert(sizeof(CUdevice) == sizeof(int));
static_assert(std::is_same_v<PFN_cuDeviceGet_v2000, DeviceGet>);
