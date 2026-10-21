extern "C" __global__ void address_control(float *out, const float *a, unsigned int n) {
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    float value = 0.0f;
    for (unsigned int j = i; j < n; j += blockDim.x * gridDim.x) value += a[j];
    if (i < n) out[i] = value;
}
