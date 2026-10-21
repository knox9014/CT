extern "C" __global__ void first(float *out, const float *a) {
    out[threadIdx.x] = a[threadIdx.x] + 1.0f;
}
extern "C" __global__ void second(unsigned long long *out, unsigned long long value) {
    out[threadIdx.x] = value ^ (unsigned long long)threadIdx.x;
}
