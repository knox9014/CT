// CT-owned positive producer control, matching the established vector-add form.
extern "C" __global__ void vector_add(const float *a, const float *b, float *out, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) out[i] = a[i] + b[i];
}
