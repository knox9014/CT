#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <vector>
__global__ void uniform_integer(unsigned *out,const unsigned *input,unsigned rounds) {
 __shared__ volatile unsigned first[128],second[128];
 unsigned t=threadIdx.x,i=blockIdx.x*blockDim.x+t,peer=(t+1u)%blockDim.x;
 unsigned v=input[i];
 #pragma unroll 1
 for(unsigned r=0;r<rounds;++r) {
  first[t]=v^0xa5a55a5au;
  __syncthreads();
  second[t]=first[peer]+17u;
  __syncthreads();
  v=second[peer]^0x3c3c3c3cu;
  __syncthreads();
 }
 out[i]=v+29u;
}
__global__ void uniform_float(float *out,const float *input,unsigned rounds) {
 __shared__ volatile float first[128],second[128];
 unsigned t=threadIdx.x,i=blockIdx.x*blockDim.x+t,peer=(t+1u)%blockDim.x;
 float v=input[i];
 #pragma unroll 1
 for(unsigned r=0;r<rounds;++r) {
  first[t]=v+1.0f;
  __syncthreads();
  second[t]=first[peer]+2.0f;
  __syncthreads();
  v=second[peer]+4.0f;
  __syncthreads();
 }
 out[i]=v+8.0f;
}
#define CHECK(x) do {cudaError_t e=(x);if(e!=cudaSuccess){std::fprintf(stderr,"shared CUDA error %d line %d\n",int(e),__LINE__);return 41;}}while(0)
int main(int argc,char **argv) {
 if(argc!=2)return 40;unsigned seed=static_cast<unsigned>(std::strtoul(argv[1],nullptr,10));
 std::vector<std::vector<unsigned>> integers;std::vector<std::vector<float>> floats;
 for(unsigned mode=0;mode<3;++mode) {
  unsigned threads=mode==2?128u:64u,blocks=mode==2?4u:mode==1?3u:2u,n=threads*blocks,rounds=mode==2?5u:mode==1?3u:0u;
  std::vector<unsigned> input(n+2,0xdeadbeefu),out(n+2,0xdeadbeefu),back(n+2);
  std::vector<float> fin(n+2,-999999.0f),fout(n+2,-999999.0f),fback(n+2);
  for(unsigned i=0;i<n;++i){input[i+1]=seed*7919u+i*1237u;fin[i+1]=float(seed%997u+i);}
  unsigned *a=nullptr,*b=nullptr;float *fa=nullptr,*fb=nullptr;size_t bytes=(n+2)*sizeof(unsigned);
  CHECK(cudaMalloc(&a,bytes));CHECK(cudaMalloc(&b,bytes));CHECK(cudaMalloc(&fa,bytes));CHECK(cudaMalloc(&fb,bytes));
  CHECK(cudaMemcpy(a,input.data(),bytes,cudaMemcpyHostToDevice));CHECK(cudaMemcpy(b,out.data(),bytes,cudaMemcpyHostToDevice));
  CHECK(cudaMemcpy(fa,fin.data(),bytes,cudaMemcpyHostToDevice));CHECK(cudaMemcpy(fb,fout.data(),bytes,cudaMemcpyHostToDevice));
  uniform_integer<<<blocks,threads>>>(b+1,a+1,rounds);CHECK(cudaGetLastError());CHECK(cudaDeviceSynchronize());
  uniform_float<<<blocks,threads>>>(fb+1,fa+1,rounds);CHECK(cudaGetLastError());CHECK(cudaDeviceSynchronize());
  CHECK(cudaMemcpy(out.data(),b,bytes,cudaMemcpyDeviceToHost));CHECK(cudaMemcpy(back.data(),a,bytes,cudaMemcpyDeviceToHost));
  CHECK(cudaMemcpy(fout.data(),fb,bytes,cudaMemcpyDeviceToHost));CHECK(cudaMemcpy(fback.data(),fa,bytes,cudaMemcpyDeviceToHost));
  if(back!=input||fback!=fin||out.front()!=0xdeadbeefu||out.back()!=0xdeadbeefu||fout.front()!=-999999.0f||fout.back()!=-999999.0f)return 42;
  for(unsigned i=0;i<n;++i) {
   unsigned j=(i/threads)*threads+(i%threads+2u*rounds)%threads;
   unsigned expected=input[j+1];
   for(unsigned q=0;q<rounds;++q)expected=((expected^0xa5a55a5au)+17u)^0x3c3c3c3cu;
   expected+=29u;
   if(out[i+1]!=expected||fout[i+1]!=fin[j+1]+float(rounds*7u+8u))return 42;
  }
  integers.emplace_back(out.begin()+1,out.end()-1);floats.emplace_back(fout.begin()+1,fout.end()-1);
  CHECK(cudaFree(a));CHECK(cudaFree(b));CHECK(cudaFree(fa));CHECK(cudaFree(fb));
 }
 std::printf("{\"status\":\"pass\",\"seed\":%u,\"integers\":[",seed);
 for(unsigned m=0;m<3;++m){if(m)std::printf(",");std::printf("[");for(size_t i=0;i<integers[m].size();++i){if(i)std::printf(",");std::printf("%u",integers[m][i]);}std::printf("]");}
 std::printf("],\"floats\":[");
 for(unsigned m=0;m<3;++m){if(m)std::printf(",");std::printf("[");for(size_t i=0;i<floats[m].size();++i){if(i)std::printf(",");std::printf("%.1f",double(floats[m][i]));}std::printf("]");}
 std::printf("]}\n");return 0;
}
