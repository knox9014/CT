#include <cuda_runtime.h>
#include <array>
#include <vector>
#include <cstdio>
#include <cstdlib>
__global__ void lifetime_add(unsigned *out,const unsigned *in) {unsigned i=threadIdx.x;out[i]=in[i]+17u;}
#define CHECK(x) do{cudaError_t e=(x);if(e!=cudaSuccess){std::fprintf(stderr,"lifetime API %d line %d\n",int(e),__LINE__);return 41;}}while(0)
#define EXPECT(x,want) do{cudaError_t e=(x);if(e!=(want)||cudaGetLastError()!=(want)){std::fprintf(stderr,"lifetime rejection line %d\n",__LINE__);return 41;}}while(0)
int main(int argc,char **argv) {
    if(argc!=3)return 40;
    unsigned seed=static_cast<unsigned>(std::strtoul(argv[1],nullptr,10));
    unsigned cycles=static_cast<unsigned>(std::strtoul(argv[2],nullptr,10));
    if((seed!=193&&seed!=731)||(cycles!=8&&cycles!=256))return 40;
    constexpr unsigned guard=0xdeadbeef;constexpr size_t bytes=34*sizeof(unsigned);
    std::vector<std::array<unsigned,70>> rows;
    unsigned stale_checks=0,recoverable_errors=0,budget_errors=0,replacements=0;
    cudaStream_t first_stream=nullptr;cudaEvent_t first_event=nullptr;
    for(unsigned cycle=0;cycle<cycles;++cycle) {
        unsigned *input=nullptr,*output=nullptr,*a=nullptr,*b=nullptr;
        CHECK(cudaMallocHost(&input,bytes));CHECK(cudaMallocHost(&output,70*sizeof(unsigned)));
        CHECK(cudaMalloc(&a,bytes));CHECK(cudaMalloc(&b,bytes));
        input[0]=input[33]=guard;
        for(unsigned i=0;i<32;++i)input[i+1]=((seed+cycle*31u)*7919u+i*1237u)^0xa5a55a5au;
        for(unsigned i=0;i<70;++i)output[i]=guard;
        CHECK(cudaMemset(a,0x5a,bytes));CHECK(cudaMemset(b,0,bytes));
        CHECK(cudaMemcpy(b,&guard,sizeof(guard),cudaMemcpyHostToDevice));
        CHECK(cudaMemcpy(b+33,&guard,sizeof(guard),cudaMemcpyHostToDevice));
        cudaStream_t invalid=nullptr;EXPECT(cudaStreamCreateWithFlags(&invalid,9),cudaErrorInvalidValue);++recoverable_errors;
        cudaStream_t stream=nullptr;cudaEvent_t event=nullptr;
        CHECK(cudaStreamCreateWithFlags(&stream,cycle%2));CHECK(cudaEventCreate(&event));
        if(!first_stream){first_stream=stream;first_event=event;}
        cudaStream_t old_stream=stream;cudaEvent_t old_event=event;
        unsigned pageable[34]={};
        EXPECT(cudaMemcpyAsync(a,pageable,bytes,cudaMemcpyHostToDevice,stream),cudaErrorNotSupported);++recoverable_errors;
        CHECK(cudaEventRecord(event,stream));
        CHECK(cudaMemcpyAsync(a,input,bytes,cudaMemcpyHostToDevice,stream));
        CHECK(cudaFreeHost(input));
        EXPECT(cudaFreeHost(input),cudaErrorInvalidValue);++recoverable_errors;input=nullptr;
        lifetime_add<<<1,32,0,stream>>>(b+1,a+1);CHECK(cudaGetLastError());
        CHECK(cudaMemcpyAsync(output+1,a,bytes,cudaMemcpyDeviceToHost,stream));
        CHECK(cudaMemcpyAsync(output+35,b,bytes,cudaMemcpyDeviceToHost,stream));
        CHECK(cudaEventRecord(event,stream)); // replace the prior event generation
        if(cycle%3==0)CHECK(cudaEventSynchronize(event));
        else if(cycle%3==1){CHECK(cudaStreamDestroy(stream));stream=nullptr;}
        else {CHECK(cudaFree(b));EXPECT(cudaFree(b),cudaErrorInvalidValue);++recoverable_errors;b=nullptr;}
        CHECK(cudaEventSynchronize(event));
        std::array<unsigned,70> row;
        for(unsigned i=0;i<70;++i)row[i]=output[i];rows.push_back(row);
        CHECK(cudaEventDestroy(event));
        if(stream)CHECK(cudaStreamDestroy(stream));
        EXPECT(cudaStreamSynchronize(old_stream),cudaErrorInvalidResourceHandle);++stale_checks;
        EXPECT(cudaStreamDestroy(old_stream),cudaErrorInvalidResourceHandle);++stale_checks;
        EXPECT(cudaEventSynchronize(old_event),cudaErrorInvalidResourceHandle);++stale_checks;
        EXPECT(cudaEventDestroy(old_event),cudaErrorInvalidResourceHandle);++stale_checks;
        CHECK(cudaFree(a));
        if(b){CHECK(cudaFree(b));EXPECT(cudaFree(b),cudaErrorInvalidValue);++recoverable_errors;}
        CHECK(cudaFreeHost(output));
    }
    cudaStream_t streams[128]={};cudaEvent_t events[128]={};
    for(unsigned i=0;i<128;++i)CHECK(cudaStreamCreateWithFlags(&streams[i],i%2));
    cudaStream_t extra_stream=nullptr;EXPECT(cudaStreamCreateWithFlags(&extra_stream,0),cudaErrorNotSupported);++budget_errors;
    for(auto stream:streams)CHECK(cudaStreamDestroy(stream));
    CHECK(cudaStreamCreateWithFlags(&extra_stream,0));if(extra_stream==first_stream)return 41;
    CHECK(cudaStreamDestroy(extra_stream));++replacements;
    for(unsigned i=0;i<128;++i)CHECK(cudaEventCreate(&events[i]));
    cudaEvent_t extra_event=nullptr;EXPECT(cudaEventCreate(&extra_event),cudaErrorNotSupported);++budget_errors;
    for(auto event:events)CHECK(cudaEventDestroy(event));
    CHECK(cudaEventCreate(&extra_event));if(extra_event==first_event)return 41;
    CHECK(cudaEventDestroy(extra_event));++replacements;
    EXPECT(cudaStreamSynchronize(first_stream),cudaErrorInvalidResourceHandle);++stale_checks;
    EXPECT(cudaEventSynchronize(first_event),cudaErrorInvalidResourceHandle);++stale_checks;
    CHECK(cudaDeviceSynchronize());
    std::printf("{\"status\":\"completed\",\"seed\":%u,\"cycles\":%u,\"stale_checks\":%u,\"recoverable_errors\":%u,\"budget_errors\":%u,\"replacements\":%u,\"cleanup\":true,\"rows\":[",seed,cycles,stale_checks,recoverable_errors,budget_errors,replacements);
    for(size_t j=0;j<rows.size();++j){if(j)std::printf(",");std::printf("[");for(unsigned i=0;i<70;++i){if(i)std::printf(",");std::printf("%u",rows[j][i]);}std::printf("]");}
    std::printf("]}\n");return 0;
}
