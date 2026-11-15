#include "bootstrap_resolver_abi.cpp"
#include <cstddef>
#include <cstdint>
using ExportQuery = CUresult (CUDAAPI *)(const void **, const CUuuid *);
static_assert(std::is_same_v<PFN_cuGetExportTable, ExportQuery>);
static_assert(sizeof(CUuuid) == 16);
struct PeerRow {
    std::uint32_t kind; std::int32_t version; std::uint64_t flags;
    std::int32_t result, status, found, value;
    unsigned char symbol[64], uuid[16];
};
static_assert(sizeof(PeerRow) == 112 && offsetof(PeerRow, uuid) == 96);
