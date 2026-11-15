#include <cuda_runtime.h>
#include <stdio.h>
extern "C" __global__ void ct_vector_add(const unsigned *a, const unsigned *b,
                                       unsigned *c, unsigned n) {
    unsigned i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) c[i] = a[i] + b[i];
}
int main(void) {
    enum { N = 17 };
    unsigned a[N], b[N], c[N], *da = 0, *db = 0, *dc = 0;
    for (unsigned i = 0; i < N; ++i) { a[i] = 3*i+1; b[i] = 7*i+5; c[i] = 0; }
    if (cudaMalloc((void**)&da, sizeof(a)) || cudaMalloc((void**)&db, sizeof(b)) ||
        cudaMalloc((void**)&dc, sizeof(c))) return 11;
    if (cudaMemcpy(da, a, sizeof(a), cudaMemcpyHostToDevice) ||
        cudaMemcpy(db, b, sizeof(b), cudaMemcpyHostToDevice)) return 12;
    ct_vector_add<<<2,16>>>(da, db, dc, N);
    if (cudaGetLastError() || cudaDeviceSynchronize() ||
        cudaMemcpy(c, dc, sizeof(c), cudaMemcpyDeviceToHost)) return 13;
    for (unsigned i = 0; i < N; ++i) if (c[i] != 10*i+6) return 14;
    if (cudaFree(da) || cudaFree(db) || cudaFree(dc)) return 15;
    puts("vector results correct");
    return 0;
}
