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
    FreeLibrary(dll);
    std::puts("Official PFN consumer: error mapping and both resolver ABI versions passed.");
}
