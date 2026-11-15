/* CT-owned genuine nvcc consumer. Python checks all numerical expectations. */
#include <cuda_runtime.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#define CHECK(x) do { if ((x) != cudaSuccess) { std::fprintf(stderr,"CUDA operation failed at line %d\n",__LINE__); return 42; } } while (0)
__device__ volatile unsigned ct_narrow = 0x80000001u;
__device__ volatile unsigned long long ct_wide_input = 0x1234567880000001ull;
__device__ volatile unsigned long long ct_wide_output = ~0ull;
extern "C" __global__ void widen_value() { ct_wide_output = ct_narrow; }
extern "C" __global__ void narrow_value() { ct_narrow = (unsigned)ct_wide_input; }
static void print64(const unsigned long long *p) {
 std::printf("["); for(unsigned i=0;i<5;i++)std::printf("%s%llu",i?",":"",p[i]); std::printf("]");
}
static void print32(const unsigned *p) {
 std::printf("["); for(unsigned i=0;i<5;i++)std::printf("%s%u",i?",":"",p[i]); std::printf("]");
}
int main(int argc,char **argv) {
 if(argc!=2)return 2;
 char *end=nullptr; unsigned long seed=std::strtoul(argv[1],&end,10);
 if(!end||*end||seed<1||seed>1000000)return 2;
 const unsigned inputs[8]={0,1,0x7fffffffu,0x80000000u,0x80000001u,0xffffffffu,(unsigned)seed*2654435761u,(unsigned)seed^0xa5a5a5a5u};
 const unsigned long long wides[4]={0,1,0xdeadbeef80000001ull,~0ull};
 size_t n=0; CHECK(cudaGetSymbolSize(&n,ct_narrow)); if(n!=4)return 3;
 CHECK(cudaGetSymbolSize(&n,ct_wide_output)); if(n!=8)return 3;
 HMODULE driver=GetModuleHandleW(L"nvcuda.dll");if(!driver)return 3;
 using Name=int(__stdcall *)(char *,int,int);
 auto get_name=reinterpret_cast<Name>(GetProcAddress(driver,"cuDeviceGetName"));if(!get_name)return 3;
 char name[256]={};if(get_name(name,sizeof(name),0)!=0)return 3;
 std::printf("{\"device\":\"");
 for(const unsigned char *p=(const unsigned char *)name;*p;p++) {
  if(*p=='"'||*p=='\\')std::printf("\\%c",*p);
  else if(*p<32)std::printf("\\u%04x",(unsigned)*p);
  else std::printf("%c",*p);
 }
 std::printf("\",\"seed\":%lu,\"rows\":[",seed);
 for(unsigned i=0;i<8;i++) {
  unsigned input=inputs[i]; unsigned long long wide=wides[(i+seed)%4]^(i>=6?((unsigned long long)seed<<32):0),poison=~0ull;
  CHECK(cudaMemcpyToSymbol(ct_narrow,&input,4));
  CHECK(cudaMemcpyToSymbol(ct_wide_output,&poison,8));
  widen_value<<<1,1>>>(); CHECK(cudaGetLastError());
  unsigned long long read64[5]; for(unsigned j=0;j<5;j++)read64[j]=0x12345678cafebabeull;
  CHECK(cudaMemcpyFromSymbol(read64+2,ct_wide_output,8));
  CHECK(cudaMemcpyToSymbol(ct_wide_input,&wide,8));
  narrow_value<<<1,1>>>(); CHECK(cudaGetLastError());
  unsigned read32[5]; for(unsigned j=0;j<5;j++)read32[j]=0xcafebabeu;
  CHECK(cudaMemcpyFromSymbol(read32+2,ct_narrow,4));
  if(i)std::printf(","); std::printf("{\"wide\":");print64(read64);std::printf(",\"narrow\":");print32(read32);std::printf("}");
 }
 CHECK(cudaDeviceSynchronize());
 std::printf("],\"main_entered\":1}\n"); return 0;
}
