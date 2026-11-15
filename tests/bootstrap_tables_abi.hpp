// TEST ONLY. Private signatures derive from the pinned public inventory.
// Official headers verify primitive types; they do not certify private semantics.
#pragma once
#include <cuda.h>
#include <cstddef>
#include <cstdint>
#include <type_traits>
struct FatbincWrapper;
struct FatbinHeader;
using Module = CUresult (CUDAAPI *)(CUmodule*, const FatbincWrapper*);
using Context = CUresult (CUDAAPI *)(CUcontext*, CUdevice);
using Primary = CUresult (CUDAAPI *)(CUdevice, std::uint32_t);
using Ext1 = CUresult (CUDAAPI *)(CUmodule*, const FatbincWrapper*, void*, void*, std::uint32_t);
using VoidSlot = void (CUDAAPI *)(std::size_t);
using Ext2 = CUresult (CUDAAPI *)(const FatbinHeader*, CUmodule*, void*, void*, std::uint32_t);
using Compiler = CUresult (CUDAAPI *)();
using Hook = void (CUDAAPI *)(void**, std::size_t*);
struct CudartTable {
    std::size_t byte_size; Module module; Context context; std::size_t hole3;
    Primary primary; std::size_t hole5; Ext1 module_ext1; VoidSlot opaque_void;
    Ext2 module_ext2; std::size_t hole9, hole10, hole11; Compiler compiler;
};
struct HooksTable {
    std::size_t byte_size, hole1; Hook first; std::size_t hole3, hole4, hole5; Hook second;
};
struct TableState { std::uint64_t mask; std::uint32_t stopped, reserved; };
static_assert(sizeof(void*)==8 && sizeof(std::size_t)==8 && sizeof(CUresult)==4 && sizeof(CUdevice)==4);
static_assert(sizeof(CUmodule)==8 && sizeof(CUcontext)==8 && sizeof(std::uint32_t)==4);
static_assert(CUDA_ERROR_NOT_SUPPORTED==801 && CUDA_ERROR_INVALID_VALUE==1);
static_assert(sizeof(CudartTable)==104 && alignof(CudartTable)==8);
static_assert(sizeof(HooksTable)==56 && alignof(HooksTable)==8);
#define SLOT(T, F, I) static_assert(offsetof(T,F)==8*(I))
SLOT(CudartTable,byte_size,0); SLOT(CudartTable,module,1); SLOT(CudartTable,context,2);
SLOT(CudartTable,hole3,3); SLOT(CudartTable,primary,4); SLOT(CudartTable,hole5,5);
SLOT(CudartTable,module_ext1,6); SLOT(CudartTable,opaque_void,7); SLOT(CudartTable,module_ext2,8);
SLOT(CudartTable,hole9,9); SLOT(CudartTable,hole10,10); SLOT(CudartTable,hole11,11); SLOT(CudartTable,compiler,12);
SLOT(HooksTable,byte_size,0); SLOT(HooksTable,hole1,1); SLOT(HooksTable,first,2); SLOT(HooksTable,hole3,3);
SLOT(HooksTable,hole4,4); SLOT(HooksTable,hole5,5); SLOT(HooksTable,second,6);
#undef SLOT
static_assert(sizeof(TableState)==16 && alignof(TableState)==8 && offsetof(TableState,stopped)==8 && offsetof(TableState,reserved)==12);
static_assert(std::is_same_v<std::invoke_result_t<VoidSlot,std::size_t>,void>);
static_assert(std::is_same_v<std::invoke_result_t<Hook,void**,std::size_t*>,void>);
