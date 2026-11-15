/* Genuine CUDA host program; Python independently owns all expected results. */
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"global test line %d\n",__LINE__);return 42; } } while(0)
__device__ volatile unsigned ct_counter=7;
__device__ volatile unsigned ct_zero;
__device__ unsigned ct_unused=29;
extern "C" __global__ void ct_read(unsigned *out,const unsigned *in,unsigned n,unsigned bias) {
 unsigned i=blockIdx.x*blockDim.x+threadIdx.x;
 if(i<n) out[i]=in[i]+ct_counter+ct_zero+bias;
}
extern "C" __global__ void ct_advance() { ct_counter=ct_counter+1;ct_zero=ct_zero+3; }
static void array(const unsigned *a,unsigned n) { std::printf("[");for(unsigned i=0;i<n;i++)std::printf("%s%u",i?",":"",a[i]);std::printf("]"); }
int main(int argc,char **argv) {
 CHECK(argc==2);unsigned seed=(unsigned)std::strtoul(argv[1],nullptr,10);CHECK(seed&&seed<=1000000);
 constexpr unsigned n=17,g=64,total=n+2*g,calls=100;
 unsigned in[total],out[total],readback[total],outputs[calls][total],errors[calls*2];
 for(unsigned i=0;i<total;i++){in[i]=(seed*5+i*7)^0x2468ace0u;out[i]=(seed*3+i*11)^0x13579bdfu;}
 unsigned *di=nullptr,*dout=nullptr;
 CHECK(cudaGetLastError()==cudaSuccess);CHECK(cudaMalloc((void**)&di,sizeof(in))==cudaSuccess);CHECK(cudaMalloc((void**)&dout,sizeof(out))==cudaSuccess);
 CHECK(cudaMemcpy(di,in,sizeof(in),cudaMemcpyHostToDevice)==cudaSuccess);CHECK(cudaMemcpy(dout,out,sizeof(out),cudaMemcpyHostToDevice)==cudaSuccess);
 for(unsigned j=0;j<calls;j++) {
  ct_read<<<1,32>>>(dout+g,di+g,n,seed%13);errors[j*2]=(unsigned)cudaGetLastError();CHECK(errors[j*2]==0);
  CHECK(cudaMemcpy(outputs[j],dout,sizeof(out),cudaMemcpyDeviceToHost)==cudaSuccess);
  ct_advance<<<1,1>>>();errors[j*2+1]=(unsigned)cudaGetLastError();CHECK(errors[j*2+1]==0);
 }
 CHECK(cudaDeviceSynchronize()==cudaSuccess);CHECK(cudaMemcpy(readback,di,sizeof(in),cudaMemcpyDeviceToHost)==cudaSuccess);
 CHECK(cudaFree(di)==cudaSuccess);CHECK(cudaFree(dout)==cudaSuccess);
 std::printf("{\"seed\":%u,\"runs\":[",seed);for(unsigned j=0;j<calls;j++){if(j)std::printf(",");array(outputs[j],total);}
 std::printf("],\"inputs\":");array(readback,total);std::printf(",\"errors\":");array(errors,calls*2);std::printf(",\"main_entered\":1}\n");return 0;
}
