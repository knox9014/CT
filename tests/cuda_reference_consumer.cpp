// Invoke the local CT DLL through NVIDIA PFN declarations, without linking CUDA.
#include <windows.h>
#include <cudaTypedefs.h>
#include <cstdio>
#include <cstring>

int wmain(int argc, wchar_t **argv) {
    if (argc != 2) return 2;
    HMODULE dll = LoadLibraryExW(argv[1], nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    if (!dll) return 1;
    auto name = reinterpret_cast<PFN_cuGetErrorName_v6000>(GetProcAddress(dll, "cuGetErrorName"));
    auto old_query = reinterpret_cast<PFN_cuGetProcAddress_v11030>(GetProcAddress(dll, "cuGetProcAddress"));
    auto new_query = reinterpret_cast<PFN_cuGetProcAddress_v12000>(GetProcAddress(dll, "cuGetProcAddress_v2"));
    auto version = reinterpret_cast<PFN_cuDriverGetVersion_v2020>(GetProcAddress(dll, "cuDriverGetVersion"));
    if (!name || !old_query || !new_query || !version) return 1;
    const char *result = nullptr;
    if (name(CUDA_ERROR_NOT_SUPPORTED, &result) != CUDA_SUCCESS || !result || std::strcmp(result, "CUDA_ERROR_NOT_SUPPORTED")) return 1;
    int v = -1;
    if (version(&v) != CUDA_ERROR_NOT_SUPPORTED || v != 0) return 1;
    void *function = nullptr;
    if (old_query("cuGetErrorName", &function, 6000, 0) || !function) return 1;
    CUdriverProcAddressQueryResult status = CU_GET_PROC_ADDRESS_VERSION_NOT_SUFFICIENT;
    if (new_query("cuGetErrorName", &function, 6000, 0, &status) || !function || status != CU_GET_PROC_ADDRESS_SUCCESS) return 1;
    if (new_query("cuGetErrorName", &function, 5999, 0, &status) || function || status != CU_GET_PROC_ADDRESS_VERSION_NOT_SUFFICIENT) return 1;
    if (old_query("ct_missing", &function, 12000, 0) != CUDA_ERROR_NOT_FOUND || function) return 1;
    if (new_query("ct_missing", &function, 12000, 0, &status) || function || status != CU_GET_PROC_ADDRESS_SYMBOL_NOT_FOUND) return 1;
    auto retain = reinterpret_cast<PFN_cuDevicePrimaryCtxRetain_v7000>(GetProcAddress(dll, "cuDevicePrimaryCtxRetain"));
    auto release = reinterpret_cast<PFN_cuDevicePrimaryCtxRelease_v11000>(GetProcAddress(dll, "cuDevicePrimaryCtxRelease_v2"));
    auto reset = reinterpret_cast<PFN_cuDevicePrimaryCtxReset_v11000>(GetProcAddress(dll, "cuDevicePrimaryCtxReset_v2"));
    auto state = reinterpret_cast<PFN_cuDevicePrimaryCtxGetState_v7000>(GetProcAddress(dll, "cuDevicePrimaryCtxGetState"));
    auto set_flags = reinterpret_cast<PFN_cuDevicePrimaryCtxSetFlags_v11000>(GetProcAddress(dll, "cuDevicePrimaryCtxSetFlags_v2"));
    auto get_flags = reinterpret_cast<PFN_cuCtxGetFlags_v7000>(GetProcAddress(dll, "cuCtxGetFlags"));
    if (!set_flags || !get_flags || GetProcAddress(dll, "cuDevicePrimaryCtxSetFlags")) return 1;
    unsigned int context_flags = 9;
    if (set_flags(0, 0) != CUDA_ERROR_NOT_INITIALIZED || get_flags(&context_flags) != CUDA_ERROR_NOT_INITIALIZED) return 1;
    if (new_query("cuDevicePrimaryCtxSetFlags", &function, 10999, 0, &status) || function || status != CU_GET_PROC_ADDRESS_VERSION_NOT_SUFFICIENT) return 1;
    if (new_query("cuDevicePrimaryCtxSetFlags", &function, 11000, 0, &status) || function != reinterpret_cast<void *>(set_flags)) return 1;
    if (new_query("cuCtxGetFlags", &function, 7000, 0, &status) || function != reinterpret_cast<void *>(get_flags)) return 1;
    if (!retain || !release || !state || !reset) return 1;
    CUcontext primary = nullptr; unsigned int primary_flags = 0; int active = 0;
    if (retain(&primary, 0) != CUDA_ERROR_NOT_INITIALIZED ||
        state(0, &primary_flags, &active) != CUDA_ERROR_NOT_INITIALIZED ||
        release(0) != CUDA_ERROR_NOT_INITIALIZED || reset(0) != CUDA_ERROR_NOT_INITIALIZED) return 1;
    if (GetProcAddress(dll, "cuDevicePrimaryCtxReset")) return 1;
    if (new_query("cuDevicePrimaryCtxReset", &function, 10999, 0, &status) || function || status != CU_GET_PROC_ADDRESS_VERSION_NOT_SUFFICIENT) return 1;
    if (new_query("cuDevicePrimaryCtxReset", &function, 11000, 0, &status) || function != reinterpret_cast<void *>(reset) || status != CU_GET_PROC_ADDRESS_SUCCESS) return 1;
    if (new_query("cuDevicePrimaryCtxRelease", &function, 10999, 0, &status) || function || status != CU_GET_PROC_ADDRESS_VERSION_NOT_SUFFICIENT) return 1;
    if (new_query("cuDevicePrimaryCtxRelease", &function, 11000, 0, &status) || function != reinterpret_cast<void *>(release) || status != CU_GET_PROC_ADDRESS_SUCCESS) return 1;
    auto copy = reinterpret_cast<PFN_cuMemcpyDtoD_v3020>(GetProcAddress(dll, "cuMemcpyDtoD_v2"));
    auto fill8 = reinterpret_cast<PFN_cuMemsetD8_v3020>(GetProcAddress(dll, "cuMemsetD8_v2"));
    auto fill16 = reinterpret_cast<PFN_cuMemsetD16_v3020>(GetProcAddress(dll, "cuMemsetD16_v2"));
    auto fill32 = reinterpret_cast<PFN_cuMemsetD32_v3020>(GetProcAddress(dll, "cuMemsetD32_v2"));
    if (!copy || !fill8 || !fill16 || !fill32) return 1;
    if (copy(0, 0, 0) != CUDA_ERROR_NOT_INITIALIZED ||
        fill8(0, 0x78, 0) != CUDA_ERROR_NOT_INITIALIZED ||
        fill16(0, 0x5678, 0) != CUDA_ERROR_NOT_INITIALIZED ||
        fill32(0, 0x12345678, 0) != CUDA_ERROR_NOT_INITIALIZED) return 1;
    auto range = reinterpret_cast<PFN_cuMemGetAddressRange_v3020>(GetProcAddress(dll, "cuMemGetAddressRange_v2"));
    auto attribute = reinterpret_cast<PFN_cuPointerGetAttribute_v4000>(GetProcAddress(dll, "cuPointerGetAttribute"));
    unsigned int managed = 99;
    if (!range || !attribute || range(nullptr, nullptr, 0) != CUDA_ERROR_NOT_INITIALIZED ||
        attribute(&managed, CU_POINTER_ATTRIBUTE_IS_MANAGED, 0) != CUDA_ERROR_NOT_INITIALIZED || managed != 99) return 1;
    FreeLibrary(dll);
    std::puts("Official PFN consumer: error mapping, resolver ABI versions and primary calls passed.");
}
