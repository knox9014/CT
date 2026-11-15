#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <cfenv>
#include <xmmintrin.h>
#include <vector>
#define FUSED_BODY {unsigned i=blockIdx.x*blockDim.x+threadIdx.x;out[i]=__fmaf_rn(a[i],b[i],c[i]);}
__global__ void fused_kernel(float *out,const float *a,const float *b,const float *c) FUSED_BODY
__global__ void renamed_fused(float *out,const float *a,const float *b,const float *c) FUSED_BODY
__global__ void split_kernel(float *out,const float *a,const float *b,const float *c) {
 unsigned i=blockIdx.x*blockDim.x+threadIdx.x;out[i]=__fadd_rn(__fmul_rn(a[i],b[i]),c[i]);
}
static unsigned fixed[16][3]={
 {0x3f800001,0x3f7ffffe,0xbf800000},{0x3f800000,0x3f800000,0x33800000},
 {0x3f800001,0x3f800000,0x33800000},{1,0x3f800000,0},{0x00800000,0x3f000000,0},
 {1,0x3f000000,0},{1,0x3f000000,1},{0x7f7fffff,0x40000000,0xff7fffff},
 {0x7f7fffff,0x40000000,0},{0x80000000,0x3f800000,0x80000000},
 {0x3f800000,0x3f800000,0xbf800000},{0x7f800000,0x3f800000,0},
 {0,0x7f800000,0},{0x7f800000,0x3f800000,0xff800000},{0x7fc12345,0x3f800000,0},
 {0x007fffff,0x3f800000,1}};
static float as_float(unsigned v){float x;std::memcpy(&x,&v,4);return x;}
static unsigned bits(float v){unsigned x;std::memcpy(&x,&v,4);return x;}
static bool nan_bits(unsigned v){return (v&0x7f800000u)==0x7f800000u&&(v&0x7fffffu)!=0;}
static bool equal_bits(unsigned a,unsigned b){return nan_bits(b)?nan_bits(a):a==b;}
#define CHECK(x) do{cudaError_t e=(x);if(e!=cudaSuccess){std::fprintf(stderr,"fma CUDA error %d line %d\n",int(e),__LINE__);return 41;}}while(0)
int main(int argc,char **argv){
 if(argc!=2)return 40;unsigned seed=static_cast<unsigned>(std::strtoul(argv[1],nullptr,10)),state=seed,inputs[32][3];
 if(std::fesetround(FE_TONEAREST)!=0)return 43;_mm_setcsr(_mm_getcsr()&~0xe040u);
 bool cpu_mode=std::fegetround()==FE_TONEAREST&&(_mm_getcsr()&0xe040u)==0;if(!cpu_mode)return 43;
 std::memcpy(inputs,fixed,sizeof(fixed));for(unsigned i=16;i<32;++i)for(unsigned k=0;k<3;++k){state^=state<<13;state^=state>>17;state^=state<<5;inputs[i][k]=state&0xff7fffffu;}
 std::vector<std::vector<unsigned>> fused,split;
 for(unsigned mode=0;mode<2;++mode){
  unsigned threads=mode?128u:64u,blocks=mode?4u:3u,n=threads*blocks;size_t bytes=(n+2)*4;
  std::vector<unsigned> a(n+2,0xdeadbeefu),b=a,c=a,out=a,separate=a,back=a;
  for(unsigned i=0;i<n;++i){unsigned j=(i+seed)%32;a[i+1]=inputs[j][0];b[i+1]=inputs[j][1];c[i+1]=inputs[j][2];}
  float *da=nullptr,*db=nullptr,*dc=nullptr,*dout=nullptr,*ds=nullptr;
  CHECK(cudaMalloc(&da,bytes));CHECK(cudaMalloc(&db,bytes));CHECK(cudaMalloc(&dc,bytes));CHECK(cudaMalloc(&dout,bytes));CHECK(cudaMalloc(&ds,bytes));
  CHECK(cudaMemcpy(da,a.data(),bytes,cudaMemcpyHostToDevice));CHECK(cudaMemcpy(db,b.data(),bytes,cudaMemcpyHostToDevice));CHECK(cudaMemcpy(dc,c.data(),bytes,cudaMemcpyHostToDevice));CHECK(cudaMemcpy(dout,out.data(),bytes,cudaMemcpyHostToDevice));CHECK(cudaMemcpy(ds,separate.data(),bytes,cudaMemcpyHostToDevice));
  if(mode)renamed_fused<<<blocks,threads>>>(dout+1,da+1,db+1,dc+1);else fused_kernel<<<blocks,threads>>>(dout+1,da+1,db+1,dc+1);
  CHECK(cudaGetLastError());CHECK(cudaDeviceSynchronize());split_kernel<<<blocks,threads>>>(ds+1,da+1,db+1,dc+1);CHECK(cudaGetLastError());CHECK(cudaDeviceSynchronize());
  CHECK(cudaMemcpy(out.data(),dout,bytes,cudaMemcpyDeviceToHost));CHECK(cudaMemcpy(separate.data(),ds,bytes,cudaMemcpyDeviceToHost));
  CHECK(cudaMemcpy(back.data(),da,bytes,cudaMemcpyDeviceToHost));if(back!=a)return 42;CHECK(cudaMemcpy(back.data(),db,bytes,cudaMemcpyDeviceToHost));if(back!=b)return 42;CHECK(cudaMemcpy(back.data(),dc,bytes,cudaMemcpyDeviceToHost));if(back!=c)return 42;
  if(out.front()!=0xdeadbeefu||out.back()!=0xdeadbeefu||separate.front()!=0xdeadbeefu||separate.back()!=0xdeadbeefu)return 42;
  if(std::fegetround()!=FE_TONEAREST||(_mm_getcsr()&0xe040u)!=0)return 43;
  for(unsigned i=0;i<n;++i){float x=as_float(a[i+1]),y=as_float(b[i+1]),z=as_float(c[i+1]);volatile float product=x*y;float sum=product+z;if(!equal_bits(out[i+1],bits(std::fma(x,y,z)))||!equal_bits(separate[i+1],bits(sum)))return 42;}
  fused.emplace_back(out.begin()+1,out.end()-1);split.emplace_back(separate.begin()+1,separate.end()-1);
  CHECK(cudaFree(da));CHECK(cudaFree(db));CHECK(cudaFree(dc));CHECK(cudaFree(dout));CHECK(cudaFree(ds));
 }
 std::printf("{\"status\":\"pass\",\"seed\":%u,\"cpu_mode\":true,\"fused\":[",seed);
 for(unsigned m=0;m<2;++m){if(m)std::printf(",");std::printf("[");for(size_t i=0;i<fused[m].size();++i){if(i)std::printf(",");std::printf("%u",fused[m][i]);}std::printf("]");}
 std::printf("],\"split\":[");for(unsigned m=0;m<2;++m){if(m)std::printf(",");std::printf("[");for(size_t i=0;i<split[m].size();++i){if(i)std::printf(",");std::printf("%u",split[m][i]);}std::printf("]");}std::printf("]}\n");return 0;
}
