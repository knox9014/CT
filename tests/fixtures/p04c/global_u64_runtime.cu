/* Genuine unchanged shared-cudart host; Python owns all numerical expectations. */
#include <cuda_runtime.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#define CHECK(x) do {if(!(x)){std::fprintf(stderr,"symbol line %d\n",__LINE__);return 42;}}while(0)
__device__ volatile unsigned long long ct_counter=0x1234567800000000ull;
__device__ volatile unsigned long long ct_other=29;
__device__ volatile unsigned ct_small=11;
extern "C" __global__ void ct_read(unsigned *out,const unsigned *in,unsigned n,unsigned bias) {
 unsigned i=blockIdx.x*blockDim.x+threadIdx.x;
 if(i<n)out[i]=in[i]+(unsigned)ct_counter+(unsigned)(ct_counter>>32)+(unsigned)ct_other+(unsigned)(ct_other>>32)+bias;
}
extern "C" __global__ void ct_advance(){ct_counter=ct_counter+0x100000001ull;ct_other=ct_other+3;ct_small=ct_small+1;}
static void wide_array(const unsigned long long *p,unsigned n){std::printf("[");for(unsigned i=0;i<n;i++)std::printf("%s%llu",i?",":"",p[i]);std::printf("]");}
static void array(const unsigned *p,unsigned n){std::printf("[");for(unsigned i=0;i<n;i++)std::printf("%s%u",i?",":"",p[i]);std::printf("]");}
static void bytes(const unsigned char *p,unsigned n){std::printf("[");for(unsigned i=0;i<n;i++)std::printf("%s%u",i?",":"",(unsigned)p[i]);std::printf("]");}
int main(int argc,char **argv) {
 CHECK(argc==3);unsigned seed=(unsigned)std::strtoul(argv[1],nullptr,10),order=(unsigned)std::strtoul(argv[2],nullptr,10);CHECK(seed&&seed<=1000000&&order<=1);
 constexpr unsigned n=17,g=64,total=n+2*g,calls=100;
 unsigned long long negative[8]={};unsigned ni=0;void *first_context=nullptr,*second_context=nullptr,*first_address=nullptr,*second_address=nullptr;
 unsigned long long first_final[2]={},revisit[2]={};
 using Current=int(__stdcall *)(void **);using Create=int(__stdcall *)(void **,unsigned,int);using Set=int(__stdcall *)(void *);using Destroy=int(__stdcall *)(void *);
 CHECK(cudaGetLastError()==cudaSuccess);
 // Initialize Runtime without loading a kernel module.
 int device=-1;CHECK(cudaGetDevice(&device)==cudaSuccess&&device==0);
 HMODULE driver=GetModuleHandleW(L"nvcuda.dll");CHECK(driver);
 auto current=reinterpret_cast<Current>(GetProcAddress(driver,"cuCtxGetCurrent"));auto create=reinterpret_cast<Create>(GetProcAddress(driver,"cuCtxCreate_v2"));
 auto set=reinterpret_cast<Set>(GetProcAddress(driver,"cuCtxSetCurrent"));auto destroy=reinterpret_cast<Destroy>(GetProcAddress(driver,"cuCtxDestroy_v2"));CHECK(current&&create&&set&&destroy);
 // cudaMalloc establishes the first primary context below, before it is queried.
 std::printf("{\"seed\":%u,\"order\":%u,\"contexts\":[",seed,order);
 for(unsigned ctx=0;ctx<2;ctx++) {
  if(ctx){CHECK(create(&second_context,0,0)==0);CHECK(second_context&&second_context!=first_context);std::printf(",");}
  unsigned in[total],out[total],bootstrap[total],inputs[total],runs[calls][total];unsigned long long before[calls][2],after[calls][2],final_values[2];
  unsigned char partial_reads[calls][2+2*g];
  for(unsigned i=0;i<total;i++){in[i]=(seed*5+ctx*23+i*7)^0x2468ace0u;out[i]=(seed*3+ctx*31+i*11)^0x13579bdfu;}
  unsigned *di=nullptr,*dout=nullptr;unsigned long long *tmp=nullptr;CHECK(cudaMalloc((void**)&di,sizeof(in))==cudaSuccess);CHECK(cudaMalloc((void**)&dout,sizeof(out))==cudaSuccess);CHECK(cudaMalloc((void**)&tmp,8)==cudaSuccess);
  CHECK(cudaMemcpy(di,in,sizeof(in),cudaMemcpyHostToDevice)==cudaSuccess);CHECK(cudaMemcpy(dout,out,sizeof(out),cudaMemcpyHostToDevice)==cudaSuccess);
  if(!ctx){CHECK(current(&first_context)==0&&first_context);}
  void *address=nullptr,*other=nullptr;size_t size=0;
  if(order==0){CHECK(cudaGetSymbolSize(&size,ct_counter)==cudaSuccess&&size==8);CHECK(cudaGetSymbolAddress(&address,ct_counter)==cudaSuccess&&address);}
  ct_read<<<1,32>>>(dout+g,di+g,n,seed%13+ctx);CHECK(cudaGetLastError()==cudaSuccess);
  CHECK(cudaMemcpy(bootstrap,dout,sizeof(out),cudaMemcpyDeviceToHost)==cudaSuccess);
  CHECK(cudaGetSymbolAddress(&address,ct_counter)==cudaSuccess&&address);CHECK(cudaGetSymbolAddress(&other,ct_other)==cudaSuccess&&other&&address!=other);
  CHECK(cudaGetSymbolSize(&size,ct_counter)==cudaSuccess&&size==8);
  if(ctx)second_address=address;else first_address=address;
  size_t small_size=0;unsigned small_value=0;CHECK(cudaGetSymbolSize(&small_size,ct_small)==cudaSuccess&&small_size==4);CHECK(cudaMemcpyFromSymbol(&small_value,ct_small,4,0,cudaMemcpyDeviceToHost)==cudaSuccess&&small_value==11);CHECK(cudaMemcpyToSymbol(ct_small,&small_value,5,0,cudaMemcpyHostToDevice)==cudaErrorInvalidValue);CHECK(cudaGetLastError()==cudaErrorInvalidValue);
  CHECK(cudaMemcpyToSymbol(ct_counter,nullptr,0,8,cudaMemcpyHostToDevice)==cudaSuccess);
  CHECK(cudaMemcpyFromSymbol(nullptr,ct_counter,0,8,cudaMemcpyDeviceToHost)==cudaSuccess);
  for(unsigned j=0;j<calls;j++) {
   unsigned long long value=(seed*17+ctx*101+j*13)^0xfffffff0a5c35a7eull;unsigned short patch=(unsigned short)(seed+ctx*31+j*19);if(j==0)value=~0ull;
   CHECK(cudaMemcpyToSymbol(ct_counter,&value,8,0,cudaMemcpyHostToDevice)==cudaSuccess);
   CHECK(cudaMemcpyToSymbol(ct_counter,&patch,2,1,cudaMemcpyHostToDevice)==cudaSuccess);
   for(unsigned k=0;k<2+2*g;k++)partial_reads[j][k]=0xa6;
   CHECK(cudaMemcpyFromSymbol(partial_reads[j]+g,ct_counter,2,1,cudaMemcpyDeviceToHost)==cudaSuccess);
   CHECK(cudaMemcpyFromSymbol(tmp,ct_counter,8,0,cudaMemcpyDeviceToDevice)==cudaSuccess);
   CHECK(cudaMemcpyToSymbol(ct_counter,tmp,8,0,cudaMemcpyDeviceToDevice)==cudaSuccess);
   CHECK(cudaMemcpyToSymbol(ct_other,address,8,0,cudaMemcpyDeviceToDevice)==cudaSuccess);
   CHECK(cudaMemcpyFromSymbol(&before[j][0],ct_counter,8,0,cudaMemcpyDeviceToHost)==cudaSuccess);
   CHECK(cudaMemcpy(&before[j][1],other,8,cudaMemcpyDeviceToHost)==cudaSuccess);
   ct_read<<<1,32>>>(dout+g,di+g,n,seed%13+ctx);CHECK(cudaGetLastError()==cudaSuccess);
   CHECK(cudaMemcpy(runs[j],dout,sizeof(out),cudaMemcpyDeviceToHost)==cudaSuccess);
   ct_advance<<<1,1>>>();CHECK(cudaGetLastError()==cudaSuccess);
   CHECK(cudaMemcpyFromSymbol(&after[j][0],ct_counter,8,0,cudaMemcpyDeviceToHost)==cudaSuccess);
   CHECK(cudaMemcpyFromSymbol(&after[j][1],ct_other,8,0,cudaMemcpyDeviceToHost)==cudaSuccess);
  }
  negative[ni++]=(unsigned)cudaMemcpyToSymbol(ct_counter,address,8,0,cudaMemcpyDeviceToDevice);CHECK(cudaGetLastError()==cudaErrorInvalidValue);
  negative[ni++]=(unsigned)cudaMemcpyFromSymbol(tmp,ct_counter,9,0,cudaMemcpyDeviceToDevice);CHECK(cudaGetLastError()==cudaErrorInvalidValue);
  unsigned long long *stale=nullptr;CHECK(cudaMalloc((void**)&stale,8)==cudaSuccess);CHECK(cudaFree(stale)==cudaSuccess);
  negative[ni++]=(unsigned)cudaMemcpyToSymbol(ct_counter,stale,8,0,cudaMemcpyDeviceToDevice);CHECK(cudaGetLastError()==cudaErrorInvalidValue);
  if(ctx){negative[ni++]=(unsigned)cudaMemcpyToSymbol(ct_counter,first_address,8,0,cudaMemcpyDeviceToDevice);CHECK(cudaGetLastError()==cudaErrorInvalidValue);}
  CHECK(cudaMemcpyFromSymbol(&final_values[0],ct_counter,8,0,cudaMemcpyDeviceToHost)==cudaSuccess);CHECK(cudaMemcpyFromSymbol(&final_values[1],ct_other,8,0,cudaMemcpyDeviceToHost)==cudaSuccess);
  unsigned small_final=0;CHECK(cudaMemcpyFromSymbol(&small_final,ct_small,4,0,cudaMemcpyDeviceToHost)==cudaSuccess);
  CHECK(cudaMemcpy(inputs,di,sizeof(in),cudaMemcpyDeviceToHost)==cudaSuccess);CHECK(cudaDeviceSynchronize()==cudaSuccess);
  CHECK(cudaFree(di)==cudaSuccess);CHECK(cudaFree(dout)==cudaSuccess);CHECK(cudaFree(tmp)==cudaSuccess);
  if(!ctx){first_final[0]=final_values[0];first_final[1]=final_values[1];}
  std::printf("{\"bootstrap\":");array(bootstrap,total);std::printf(",\"runs\":[");for(unsigned j=0;j<calls;j++){if(j)std::printf(",");array(runs[j],total);}
  std::printf("],\"inputs\":");array(inputs,total);std::printf(",\"before\":[");for(unsigned j=0;j<calls;j++){if(j)std::printf(",");wide_array(before[j],2);}
  std::printf("],\"after\":[");for(unsigned j=0;j<calls;j++){if(j)std::printf(",");wide_array(after[j],2);}
  std::printf("],\"partial_reads\":[");for(unsigned j=0;j<calls;j++){if(j)std::printf(",");bytes(partial_reads[j],2+2*g);}
  std::printf("],\"final\":");wide_array(final_values,2);std::printf(",\"small_final\":%u}",small_final);
 }
 CHECK(destroy(second_context)==0);CHECK(set(first_context)==0);
 negative[ni++]=(unsigned)cudaMemcpyToSymbol(ct_counter,second_address,8,0,cudaMemcpyDeviceToDevice);CHECK(cudaGetLastError()==cudaErrorInvalidValue);CHECK(ni==8);
 CHECK(cudaMemcpyFromSymbol(&revisit[0],ct_counter,8,0,cudaMemcpyDeviceToHost)==cudaSuccess);CHECK(cudaMemcpyFromSymbol(&revisit[1],ct_other,8,0,cudaMemcpyDeviceToHost)==cudaSuccess);
 (void)first_final;
 std::printf("],\"negative\":");wide_array(negative,8);std::printf(",\"revisit\":");wide_array(revisit,2);std::printf(",\"main_entered\":1}\n");return 0;
}
