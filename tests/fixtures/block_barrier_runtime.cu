#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <vector>
#define EXCHANGE_BODY { \
 unsigned t=threadIdx.x,base=blockIdx.x*blockDim.x,i=base+t; \
 scratch[i]=input[i]^0xa5a55a5au; \
 __syncthreads(); \
 unsigned peer=base+(t+1u)%blockDim.x; \
 unsigned v=scratch[peer]+17u;out[i]=v; \
 __syncthreads(); \
 scratch[i]=v^0x3c3c3c3cu; \
 __syncthreads(); \
 out[i]=scratch[peer]+29u; \
}
__global__ void rendezvous(unsigned *scratch,unsigned *out,const unsigned *input) EXCHANGE_BODY
__global__ void renamed_exchange(unsigned *scratch,unsigned *out,const unsigned *input) EXCHANGE_BODY
#define CHECK(x) do {cudaError_t e=(x);if(e!=cudaSuccess){std::fprintf(stderr,"barrier CUDA error %d line %d\n",int(e),__LINE__);return 41;}}while(0)
int main(int argc,char **argv) {
 if(argc!=2)return 40;unsigned seed=static_cast<unsigned>(std::strtoul(argv[1],nullptr,10));
 std::vector<std::vector<unsigned>> results;
 for(unsigned mode=0;mode<2;++mode) {
  unsigned threads=mode?128u:64u,blocks=mode?4u:3u,n=threads*blocks;
  std::vector<unsigned> input(n+2,0xdeadbeefu),out(n+2,0xdeadbeefu),scratch(n+2,0xdeadbeefu),back(n+2);
  for(unsigned i=0;i<n;++i)input[i+1]=seed*7919u+i*1237u;
  unsigned *a=nullptr,*b=nullptr,*c=nullptr;size_t bytes=(n+2)*sizeof(unsigned);
  CHECK(cudaMalloc(&a,bytes));CHECK(cudaMalloc(&b,bytes));CHECK(cudaMalloc(&c,bytes));
  CHECK(cudaMemcpy(a,input.data(),bytes,cudaMemcpyHostToDevice));CHECK(cudaMemcpy(b,out.data(),bytes,cudaMemcpyHostToDevice));CHECK(cudaMemcpy(c,scratch.data(),bytes,cudaMemcpyHostToDevice));
  if(mode)renamed_exchange<<<blocks,threads>>>(c+1,b+1,a+1);
  else rendezvous<<<blocks,threads>>>(c+1,b+1,a+1);
  CHECK(cudaGetLastError());CHECK(cudaDeviceSynchronize());
  CHECK(cudaMemcpy(out.data(),b,bytes,cudaMemcpyDeviceToHost));CHECK(cudaMemcpy(scratch.data(),c,bytes,cudaMemcpyDeviceToHost));CHECK(cudaMemcpy(back.data(),a,bytes,cudaMemcpyDeviceToHost));
  if(back!=input||out[0]!=0xdeadbeefu||out[n+1]!=0xdeadbeefu||scratch[0]!=0xdeadbeefu||scratch[n+1]!=0xdeadbeefu)return 42;
  for(unsigned i=0;i<n;++i) {
   unsigned base=(i/threads)*threads,t=i%threads;
   unsigned expected=(((input[base+(t+2u)%threads+1]^0xa5a55a5au)+17u)^0x3c3c3c3cu)+29u;
   unsigned published=((input[base+(t+1u)%threads+1]^0xa5a55a5au)+17u)^0x3c3c3c3cu;
   if(out[i+1]!=expected||scratch[i+1]!=published)return 42;
  }
  results.emplace_back(out.begin()+1,out.end()-1);CHECK(cudaFree(a));CHECK(cudaFree(b));CHECK(cudaFree(c));
 }
 std::printf("{\"status\":\"pass\",\"seed\":%u,\"results\":[",seed);
 for(unsigned m=0;m<2;++m) {if(m)std::printf(",");std::printf("[");for(size_t i=0;i<results[m].size();++i){if(i)std::printf(",");std::printf("%u",results[m][i]);}std::printf("]");}
 std::printf("]}\n");return 0;
}
