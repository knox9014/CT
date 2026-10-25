#include <cuda_runtime.h>
static __global__ void ct_same(const unsigned *in,unsigned *out,unsigned n,unsigned bias) {
    unsigned i=blockIdx.x*blockDim.x+threadIdx.x;
    if(i<n)out[i]=in[i]*3+bias;
}
extern "C" void ct_run_b(const unsigned *in,unsigned *out,unsigned n) {
    ct_same<<<2,16>>>(in,out,n,9);
}
