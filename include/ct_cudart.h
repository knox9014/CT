#ifndef CT_CUDART_H
#define CT_CUDART_H
#include <stddef.h>
#if defined(_WIN32)
#define CT_RUNTIME_API __stdcall
#else
#define CT_RUNTIME_API
#endif
#ifdef __cplusplus
extern "C" {
#endif
int CT_RUNTIME_API cudaGetDeviceCount(int *);
int CT_RUNTIME_API cudaGetDevice(int *);
int CT_RUNTIME_API cudaSetDevice(int);
int CT_RUNTIME_API cudaDeviceSynchronize(void);
int CT_RUNTIME_API cudaMalloc(void **, size_t);
int CT_RUNTIME_API cudaFree(void *);
int CT_RUNTIME_API cudaMemcpy(void *, const void *, size_t, int);
int CT_RUNTIME_API cudaMemset(void *, int, size_t);
int CT_RUNTIME_API cudaGetLastError(void);
int CT_RUNTIME_API cudaPeekAtLastError(void);
const char * CT_RUNTIME_API cudaGetErrorName(int);
const char * CT_RUNTIME_API cudaGetErrorString(int);
int CT_RUNTIME_API cudaDriverGetVersion(int *);
int CT_RUNTIME_API cudaRuntimeGetVersion(int *);
#ifdef __cplusplus
}
#endif
#endif
