/* Current C negative: actual-used u64 storage remains unsupported by P04a. */
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#define CHECK(x) do{if(!(x)){std::fprintf(stderr,"global contract %d\n",__LINE__);return 42;}}while(0)
__device__ volatile unsigned long long ct_used_global=7;
extern "C" __global__ void ct_global_read(unsigned long long *out){out[0]=ct_used_global;}
int main(int argc,char **argv){
 CHECK(argc==3);unsigned seed=(unsigned)std::strtoul(argv[2],nullptr,10);CHECK(seed&&seed<=1000000);
 CHECK(cudaGetLastError()==cudaSuccess);unsigned long long *p=nullptr;CHECK(cudaMalloc((void**)&p,8)==cudaSuccess);
 ct_global_read<<<1,1>>>(p);CHECK(cudaGetLastError()==cudaErrorNotSupported);
 CHECK(cudaDeviceSynchronize()==cudaSuccess);CHECK(cudaFree(p)==cudaSuccess);
 std::printf("{\"seed\":%u,\"mode\":\"used_global\",\"errors\":[801],\"runs\":[],\"main_entered\":1}\n",seed);return 0;
}
