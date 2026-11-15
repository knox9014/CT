#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
__global__ void stream_add(unsigned *out,const unsigned *in) {
    unsigned i=threadIdx.x;out[i]=in[i]+17u;
}
#define CHECK(x) do {cudaError_t e=(x); if(e!=cudaSuccess) {std::fprintf(stderr,"owned stream CUDA error %d line %d\n",int(e),__LINE__);return 41;}} while(0)
int main(int argc,char **argv) {
    if(argc!=2)return 40;
    unsigned seed=static_cast<unsigned>(std::strtoul(argv[1],nullptr,10));
    unsigned *input=nullptr,*output=nullptr;
    CHECK(cudaMallocHost(&input,32*sizeof(unsigned)));CHECK(cudaMallocHost(&output,34*sizeof(unsigned)));
    for(unsigned i=0;i<32;++i)input[i]=(seed*7919u+i*1237u)^0xa5a55a5au;
    unsigned *a=nullptr,*b=nullptr;CHECK(cudaMalloc(&a,32*sizeof(unsigned)));CHECK(cudaMalloc(&b,32*sizeof(unsigned)));
    CHECK(cudaMemcpy(a,input,32*sizeof(unsigned),cudaMemcpyHostToDevice));
    unsigned completed=0;
    for(unsigned flags=0;flags<=1;++flags) {
        cudaStream_t stream=nullptr;CHECK(cudaStreamCreateWithFlags(&stream,flags));if(!stream)return 42;
        CHECK(cudaMemset(b,0,32*sizeof(unsigned)));
        stream_add<<<1,32,0,stream>>>(b,a);CHECK(cudaGetLastError());
        CHECK(cudaStreamSynchronize(stream));
        for(unsigned i=0;i<34;++i)output[i]=0xdeadbeef;
        CHECK(cudaMemcpy(output+1,b,32*sizeof(unsigned),cudaMemcpyDeviceToHost));
        if(output[0]!=0xdeadbeef || output[33]!=0xdeadbeef)return 42;
        for(unsigned i=0;i<32;++i)if(output[i+1]!=input[i]+17u)return 42;
        CHECK(cudaStreamDestroy(stream));
        if(cudaStreamSynchronize(stream)!=cudaErrorInvalidResourceHandle)return 42;
        if(cudaGetLastError()!=cudaErrorInvalidResourceHandle)return 42;
        if(cudaStreamDestroy(stream)!=cudaErrorInvalidResourceHandle)return 42;
        if(cudaGetLastError()!=cudaErrorInvalidResourceHandle)return 42;
        ++completed;
    }
    CHECK(cudaFree(a));CHECK(cudaFree(b));CHECK(cudaFreeHost(input));CHECK(cudaFreeHost(output));
    std::printf("{\"status\":\"pass\",\"seed\":%u,\"elements\":32,\"streams\":%u}\n",seed,completed);
    return 0;
}
