/* Genuine mixed-width pointer consumer; observations only, Python owns expectations. */
#include <cuda_runtime.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#define CHECK(x) do {if((x)!=cudaSuccess){std::fprintf(stderr,"CUDA operation failed at line %d\n",__LINE__);return 42;}}while(0)
extern "C" __global__ void widen_array(unsigned long long *out,const unsigned *in,unsigned n) {
 unsigned i=blockIdx.x*blockDim.x+threadIdx.x; if(i<n)out[i]=in[i];
}
extern "C" __global__ void copy_narrow(unsigned *out,const unsigned *in,unsigned n) {
 unsigned i=blockIdx.x*blockDim.x+threadIdx.x; if(i<n)out[i]=in[i];
}
static void array32(const unsigned *v,unsigned n){std::printf("[");for(unsigned i=0;i<n;i++)std::printf("%s%u",i?",":"",v[i]);std::printf("]");}
static void array64(const unsigned long long *v,unsigned n){std::printf("[");for(unsigned i=0;i<n;i++)std::printf("%s%llu",i?",":"",v[i]);std::printf("]");}
int main(int argc,char **argv) {
 if(argc!=2)return 2;char *end=nullptr;unsigned long seed=std::strtoul(argv[1],&end,10);if(!end||*end||seed<1||seed>1000000)return 2;
 constexpr unsigned n=17,g=64,total=n+2*g+2;
 unsigned input[total],narrow[total],input_copy[total];unsigned long long output[total],negative[total];
 const unsigned edges[6]={0,1,0x7fffffffu,0x80000000u,0x80000001u,0xffffffffu};
 for(unsigned i=0;i<total;i++){input[i]=0xcafebabeu;narrow[i]=0xcafebabeu;output[i]=0xdeadbeefcafebabeull;}
 for(unsigned i=0;i<n;i++){input[g+1+i]=i<6?edges[i]:((unsigned)seed*17+i*2654435761u);narrow[g+1+i]=~input[g+1+i];output[g+i]=~(unsigned long long)input[g+1+i];}
 unsigned *di=nullptr,*dn=nullptr;unsigned long long *dw=nullptr;
 CHECK(cudaMalloc((void**)&di,sizeof(input)));CHECK(cudaMalloc((void**)&dn,sizeof(narrow)));CHECK(cudaMalloc((void**)&dw,sizeof(output)));
 CHECK(cudaMemcpy(di,input,sizeof(input),cudaMemcpyHostToDevice));CHECK(cudaMemcpy(dn,narrow,sizeof(narrow),cudaMemcpyHostToDevice));CHECK(cudaMemcpy(dw,output,sizeof(output),cudaMemcpyHostToDevice));
 // Misaligned wide argument must fail before native execution under CT's contract.
 widen_array<<<1,32>>>((unsigned long long *)((char *)dw+4),di+g+1,n);
 unsigned invalid=(unsigned)cudaGetLastError();CHECK(cudaMemcpy(negative,dw,sizeof(negative),cudaMemcpyDeviceToHost));
 widen_array<<<1,32>>>(dw+g,di+g+1,n);CHECK(cudaGetLastError());
 copy_narrow<<<1,32>>>(dn+g+1,di+g+1,n);CHECK(cudaGetLastError());
 CHECK(cudaMemcpy(output,dw,sizeof(output),cudaMemcpyDeviceToHost));CHECK(cudaMemcpy(narrow,dn,sizeof(narrow),cudaMemcpyDeviceToHost));CHECK(cudaMemcpy(input_copy,di,sizeof(input_copy),cudaMemcpyDeviceToHost));
 HMODULE driver=GetModuleHandleW(L"nvcuda.dll");if(!driver)return 3;using Name=int(__stdcall *)(char *,int,int);
 auto get_name=reinterpret_cast<Name>(GetProcAddress(driver,"cuDeviceGetName"));char name[256]={};if(!get_name||get_name(name,sizeof(name),0))return 3;
 CHECK(cudaDeviceSynchronize());CHECK(cudaFree(di));CHECK(cudaFree(dn));CHECK(cudaFree(dw));
 std::printf("{\"device\":\"");for(const unsigned char *p=(const unsigned char *)name;*p;p++){if(*p=='"'||*p=='\\')std::printf("\\%c",*p);else if(*p<32)std::printf("\\u%04x",(unsigned)*p);else std::printf("%c",*p);}
 std::printf("\",\"seed\":%lu,\"invalid\":%u,\"negative\":",seed,invalid);array64(negative,total);std::printf(",\"wide\":");array64(output,total);std::printf(",\"narrow\":");array32(narrow,total);std::printf(",\"input\":");array32(input_copy,total);std::printf("}\n");return 0;
}
