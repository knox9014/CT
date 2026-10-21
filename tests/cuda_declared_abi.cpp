// CT-header-only translation unit: generated declarations stay synchronized.
#include "../include/ct_cuda.h"
#include "cuda_abi_probe.hpp"

int main() {
    std::puts("ABI:windows-x64");
#define PROBE(name, args) abi_function(#name, static_cast<PFN_##name>(nullptr));
    CT_DRIVER_FUNCTIONS(PROBE)
#undef PROBE
    // These values are the existing CT error mapping / resolver contract.
    std::puts("enums:0:1:2:3:100:101:201:218:400:500:801:999");
    std::puts("query:0:1:2");
    std::puts("primary-errors:709");
    std::puts("attributes:1:2:3:4:5:6:7:20:0");
}
