// Compile-only proof against the pinned NVIDIA12.9 headers; no implementation copied.
#include <cuda.h>
#include <cudaTypedefs.h>
#include <type_traits>
using Init = CUresult (CUDAAPI *)(unsigned int);
using IntQuery = CUresult (CUDAAPI *)(int *);
using Resolver1 = CUresult (CUDAAPI *)(const char *, void **, int, cuuint64_t);
using Resolver2 = CUresult (CUDAAPI *)(const char *, void **, int, cuuint64_t, CUdriverProcAddressQueryResult *);
static_assert(sizeof(CUresult) == sizeof(int));
static_assert(std::is_same_v<PFN_cuInit, Init>);
static_assert(std::is_same_v<PFN_cuDriverGetVersion, IntQuery>);
static_assert(std::is_same_v<PFN_cuDeviceGetCount, IntQuery>);
static_assert(std::is_same_v<PFN_cuGetProcAddress_v11030, Resolver1>);
static_assert(std::is_same_v<PFN_cuGetProcAddress, Resolver2>);
