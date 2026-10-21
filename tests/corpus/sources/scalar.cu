// CT-owned source: compiler output is preserved byte-for-byte in local cache.
extern "C" __global__ void scalar(unsigned long long *out, long long value) {
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    long long x = value + (long long)i;
    out[i] = (unsigned long long)(x < 0 ? -x : x);
}
