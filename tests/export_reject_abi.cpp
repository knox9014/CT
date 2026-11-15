// Compile-only public signature check against the pinned official headers.
#include "real_bootstrap_abi.cpp"
using ExportQuery = CUresult (CUDAAPI *)(const void **, const CUuuid *);
static_assert(sizeof(CUuuid) == 16);
static_assert(std::is_same_v<PFN_cuGetExportTable_v3000, ExportQuery>);
