#ifndef CT_CUDART_H
#define CT_CUDART_H
#include <stddef.h>
typedef struct CT_dim3 { unsigned x, y, z; } CT_dim3;
typedef struct CT_uint3 { unsigned x, y, z; } CT_uint3;
typedef struct CT_CUstream_st *CT_cudaStream_t;
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
void ** CT_RUNTIME_API __cudaRegisterFatBinary(void *);
void CT_RUNTIME_API __cudaRegisterFatBinaryEnd(void **);
void CT_RUNTIME_API __cudaUnregisterFatBinary(void **);
void CT_RUNTIME_API __cudaRegisterFunction(void **, const char *, char *, const char *, int,
                                         CT_uint3 *, CT_uint3 *, CT_dim3 *, CT_dim3 *, int *);
void CT_RUNTIME_API __cudaRegisterVar(void **, char *, char *, const char *, int, size_t, int, int);
unsigned CT_RUNTIME_API __cudaPushCallConfiguration(CT_dim3, CT_dim3, size_t, CT_cudaStream_t);
int CT_RUNTIME_API __cudaPopCallConfiguration(CT_dim3 *, CT_dim3 *, size_t *, void *);
int CT_RUNTIME_API cudaLaunchKernel(const void *, CT_dim3, CT_dim3, void **, size_t, CT_cudaStream_t);
#ifdef __cplusplus
}
#endif
#endif
