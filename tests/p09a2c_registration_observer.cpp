/* CPU-only producer observer; allocation deliberately fails. Never CT execution. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
// Independent observed ABI types; real vendor/CT/Rust ABI is a separate gate.
struct dim3 {unsigned x,y,z;};struct uint3 {unsigned x,y,z;};
using cudaStream_t=void *;using cudaError_t=int;enum cudaMemcpyKind {unused_kind=0};
static constexpr int cudaErrorNotSupported=801;
#define CUDARTAPI __stdcall
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#define API extern "C" __declspec(dllexport)
static void *tokens[16];static unsigned token_count,image_count;
static void hex(const char *p){std::putchar('"');if(p)for(unsigned i=0;i<=1024&&p[i];i++)std::printf("%02x",(unsigned char)p[i]);std::putchar('"');}
static void image(const unsigned char *p){
 uint32_t magic=0;uint64_t bytes=0;if(!p)std::abort();std::memcpy(&magic,p,4);std::memcpy(&bytes,p+8,8);
 if(magic!=0xba55ed50||bytes>16777200)std::abort();char name[64];std::snprintf(name,sizeof(name),"raw-%u.bin",image_count);
 FILE *f=nullptr;fopen_s(&f,name,"wb");if(!f)std::abort();if(std::fwrite(p,1,(size_t)bytes+16,f)!=bytes+16)std::abort();std::fclose(f);
 std::printf("{\"kind\":\"image\",\"index\":%u,\"size\":%llu}\n",image_count++,(unsigned long long)bytes+16);
}
API void ** CUDARTAPI __cudaRegisterFatBinary(void *p){
 struct Wrapper{uint32_t magic,version;const unsigned char *data;const unsigned char **extra;};auto w=(Wrapper*)p;
 if(!w||w->magic!=0x466243b1||token_count==16)std::abort();std::printf("{\"kind\":\"wrapper\",\"version\":%u}\n",w->version);image(w->data);
 if(w->version==2){if(!w->extra)std::abort();unsigned i=0;for(;i<32&&w->extra[i];i++)image(w->extra[i]);if(w->extra[i])std::abort();std::printf("{\"kind\":\"linked\",\"count\":%u}\n",i);}
 return &tokens[token_count++];
}
API void CUDARTAPI __cudaRegisterFatBinaryEnd(void **){std::puts("{\"kind\":\"end\"}");}
API void CUDARTAPI __cudaUnregisterFatBinary(void **){std::puts("{\"kind\":\"retire\"}");}
API void CUDARTAPI __cudaRegisterFunction(void **,const char *host,char *address,const char *name,int limit,uint3 *t,uint3 *b,dim3 *bd,dim3 *gd,int *warp){
 std::printf("{\"kind\":\"function\",\"limit\":%d,\"optional\":%d,\"equal\":%d,\"host\":%d}\n",limit,(t!=nullptr)||(b!=nullptr)||(bd!=nullptr)||(gd!=nullptr)||(warp!=nullptr),address&&name&&std::strcmp(address,name)==0,host!=nullptr);
}
API void CUDARTAPI __cudaRegisterVar(void **,char *host,char *address,const char *name,int ext,size_t size,int constant,int global){
 std::printf("{\"kind\":\"variable\",\"host\":%d,\"external\":%d,\"size\":%llu,\"constant\":%d,\"global\":%d,\"address\":",host!=nullptr,ext,(unsigned long long)size,constant,global);hex(address);std::printf(",\"name\":");hex(name);std::puts("}");
}
API unsigned CUDARTAPI __cudaPushCallConfiguration(dim3,dim3,size_t,cudaStream_t){return 801;}
API cudaError_t CUDARTAPI __cudaPopCallConfiguration(dim3*,dim3*,size_t*,void*){return cudaErrorNotSupported;}
API cudaError_t CUDARTAPI cudaLaunchKernel(const void*,dim3,dim3,void**,size_t,cudaStream_t){return cudaErrorNotSupported;}
API cudaError_t CUDARTAPI cudaMalloc(void **p,size_t){*p=nullptr;return cudaErrorNotSupported;}
API cudaError_t CUDARTAPI cudaFree(void*){return cudaErrorNotSupported;}
API cudaError_t CUDARTAPI cudaMemcpy(void*,const void*,size_t,cudaMemcpyKind){return cudaErrorNotSupported;}
API cudaError_t CUDARTAPI cudaDeviceSynchronize(){return cudaErrorNotSupported;}
API cudaError_t CUDARTAPI cudaGetLastError(){return cudaErrorNotSupported;}
