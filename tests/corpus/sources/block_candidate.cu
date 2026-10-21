extern "C" __global__ void block_candidate(float *out, const float *a) {
    __shared__ float values[256];
    unsigned int i = threadIdx.x;
    values[i] = a[i];
    __syncthreads();
    out[i] = values[255 - i];
}
