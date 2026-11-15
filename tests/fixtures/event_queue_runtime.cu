#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
__global__ void queued_add(unsigned *out,const unsigned *in){unsigned i=threadIdx.x;out[i]=in[i]+17u;}
#define CHECK(x) do{cudaError_t e=(x);if(e!=cudaSuccess){std::fprintf(stderr,"queued CUDA error %d line %d\n",int(e),__LINE__);return 41;}}while(0)
int main(int argc,char **argv){
    if(argc!=2)return 40;unsigned seed=static_cast<unsigned>(std::strtoul(argv[1],nullptr,10));
    unsigned results[3][32];
    for(unsigned mode=0;mode<3;++mode){
        unsigned *input=nullptr,*output=nullptr,*a=nullptr,*b=nullptr;
        CHECK(cudaMallocHost(&input,32*sizeof(unsigned)));CHECK(cudaMallocHost(&output,34*sizeof(unsigned)));
        CHECK(cudaMalloc(&a,32*sizeof(unsigned)));CHECK(cudaMalloc(&b,32*sizeof(unsigned)));
        for(unsigned i=0;i<32;++i)input[i]=((seed+mode*31u)*7919u+i*1237u)^0xa5a55a5au;
        for(unsigned i=0;i<34;++i)output[i]=0xdeadbeef;
        cudaStream_t stream=nullptr;if(mode<2)CHECK(cudaStreamCreateWithFlags(&stream,mode));
        unsigned pageable[32]={};
        if(cudaMemcpyAsync(a,pageable,32*sizeof(unsigned),cudaMemcpyHostToDevice,stream)!=cudaErrorNotSupported)return 42;
        if(cudaGetLastError()!=cudaErrorNotSupported)return 42;
        cudaEvent_t start=nullptr,stop=nullptr;CHECK(cudaEventCreate(&start));CHECK(cudaEventCreate(&stop));
        CHECK(cudaEventRecord(start,stream));
        CHECK(cudaMemcpyAsync(a,input,32*sizeof(unsigned),cudaMemcpyHostToDevice,stream));
        // This must wait before releasing source storage still owned by the queued job.
        CHECK(cudaFreeHost(input));
        CHECK(cudaMemcpyAsync(b,a,32*sizeof(unsigned),cudaMemcpyDeviceToDevice,stream));
        queued_add<<<1,32,0,stream>>>(b,b);CHECK(cudaGetLastError());
        CHECK(cudaMemcpyAsync(output+1,b,32*sizeof(unsigned),cudaMemcpyDeviceToHost,stream));
        CHECK(cudaEventRecord(stop,stream));
        if(mode==0)CHECK(cudaEventSynchronize(stop));
        else if(mode==1)CHECK(cudaDeviceSynchronize());
        else {CHECK(cudaFree(a));a=nullptr;} // Device free is also a completion fence.
        float milliseconds=-1;CHECK(cudaEventElapsedTime(&milliseconds,start,stop));if(!(milliseconds>0))return 43;
        CHECK(cudaEventDestroy(start));CHECK(cudaEventDestroy(stop));
        if(output[0]!=0xdeadbeef||output[33]!=0xdeadbeef)return 42;
        for(unsigned i=0;i<32;++i){
            unsigned expected=(((seed+mode*31u)*7919u+i*1237u)^0xa5a55a5au)+17u;
            if(output[i+1]!=expected)return 42;results[mode][i]=output[i+1];
        }
        if(mode<2)CHECK(cudaStreamDestroy(stream));
        if(a)CHECK(cudaFree(a));CHECK(cudaFree(b));CHECK(cudaFreeHost(output));
    }
    std::printf("{\"status\":\"pass\",\"seed\":%u,\"results\":[",seed);
    for(unsigned mode=0;mode<3;++mode){if(mode)std::printf(",");std::printf("[");for(unsigned i=0;i<32;++i){if(i)std::printf(",");std::printf("%u",results[mode][i]);}std::printf("]");}
    std::printf("]}\n");return 0;
}
