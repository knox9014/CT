/* CT-owned consumer; declarations come exclusively from NVIDIA headers. */
#include <windows.h>
#include <cudaTypedefs.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
struct API {
    PFN_cuInit init; PFN_cuCtxCreate_v3020 create; PFN_cuCtxDestroy destroy;
    PFN_cuCtxSetCurrent set; PFN_cuMemAlloc allocate; PFN_cuMemFree free;
    PFN_cuMemcpyHtoD write; PFN_cuMemcpyDtoH read; PFN_cuMemcpyDtoD_v3020 copy;
    PFN_cuMemsetD8_v3020 fill8; PFN_cuMemsetD16_v3020 fill16; PFN_cuMemsetD32_v3020 fill32;
    PFN_cuGetProcAddress_v12000 query;
} api;
static unsigned int cases,checked_bytes,rejections;
#define REQUIRE(x) do {if(!(x)){fprintf(stderr,"memory check failed at line %d\n",__LINE__);return 3;}}while(0)
#define OK(x) REQUIRE((x)==CUDA_SUCCESS)
#define INVALID(x) do {CUresult code=(x);if(code!=CUDA_ERROR_INVALID_VALUE){fprintf(stderr,"unexpected code %d: %s at line %d\n",(int)code,#x,__LINE__);return 3;}++rejections;}while(0)
static int verify(CUdeviceptr device,const unsigned char *expected) {
    unsigned char observed[512];memset(observed,0x5a,sizeof(observed));
    OK(api.read(observed,device,sizeof(observed)));REQUIRE(memcmp(observed,expected,sizeof(observed))==0);
    checked_bytes+=512;return 0;
}
int main(void) {
    HMODULE driver;CUcontext context=NULL,other=NULL;CUdeviceptr source=0,destination=0,foreign=0,unowned=0;
    unsigned char input[512],expected[512];size_t i,j,k,n;unsigned int width,value;
    const size_t lengths[]={0,1,2,3,7,16,63,128,257},counts[]={0,1,3,31,89};
    const unsigned int values[]={0,0xffffffffu,0x12345678u};
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOOPENFILEERRORBOX);
    driver=LoadLibraryW(L"nvcuda.dll");if(!driver)return 41;
#define LOAD(field,type,name) api.field=(type)GetProcAddress(driver,name);if(!api.field){fputs("missing memory export\n",stderr);return 42;}
    LOAD(init,PFN_cuInit,"cuInit");LOAD(create,PFN_cuCtxCreate_v3020,"cuCtxCreate_v2");
    LOAD(destroy,PFN_cuCtxDestroy,"cuCtxDestroy_v2");LOAD(set,PFN_cuCtxSetCurrent,"cuCtxSetCurrent");
    LOAD(allocate,PFN_cuMemAlloc,"cuMemAlloc_v2");LOAD(free,PFN_cuMemFree,"cuMemFree_v2");
    LOAD(write,PFN_cuMemcpyHtoD,"cuMemcpyHtoD_v2");LOAD(read,PFN_cuMemcpyDtoH,"cuMemcpyDtoH_v2");
    LOAD(copy,PFN_cuMemcpyDtoD_v3020,"cuMemcpyDtoD_v2");LOAD(fill8,PFN_cuMemsetD8_v3020,"cuMemsetD8_v2");
    LOAD(fill16,PFN_cuMemsetD16_v3020,"cuMemsetD16_v2");LOAD(fill32,PFN_cuMemsetD32_v3020,"cuMemsetD32_v2");
    LOAD(query,PFN_cuGetProcAddress_v12000,"cuGetProcAddress_v2");
#undef LOAD
    REQUIRE(api.copy(0,0,0)==3);REQUIRE(api.fill32(0,0,0)==3);OK(api.init(0));
    REQUIRE(api.copy(0,0,0)==201);REQUIRE(api.fill8(0,0,0)==201);
    { const char *names[]={"cuMemcpyDtoD","cuMemsetD8","cuMemsetD16","cuMemsetD32"};
      const char *exports[]={"cuMemcpyDtoD_v2","cuMemsetD8_v2","cuMemsetD16_v2","cuMemsetD32_v2"};
      for(i=0;i<4;++i){void *function=NULL;CUdriverProcAddressQueryResult status;
        OK(api.query(names[i],&function,3020,0,&status));REQUIRE(status==0 && function==(void*)GetProcAddress(driver,exports[i]));
        OK(api.query(names[i],&function,3019,0,&status));REQUIRE(!function && status==2);
        REQUIRE(api.query(names[i],&function,12000,2,&status)==801 && !function);
      }}
    OK(api.create(&context,0,0));OK(api.allocate(&source,512));OK(api.allocate(&destination,512));unowned=(source>destination?source:destination)+512;
    for(i=0;i<sizeof(lengths)/sizeof(lengths[0]);++i){
        n=lengths[i];for(j=0;j<512;++j)input[j]=(unsigned char)(j*29+i*17);
        memset(expected,0xcd,512);OK(api.write(source,input,512));OK(api.write(destination,expected,512));
        OK(api.copy(destination+31,source+17,n));memcpy(expected+31,input+17,n);
        OK(verify(destination,expected));OK(verify(source,input));++cases;
    }
    /* Adjacent regions in one allocation are allowed; overlapping regions are not. */
    OK(api.copy(source+64,source,64));memcpy(input+64,input,64);OK(verify(source,input));++cases;
    for(width=1;width<=4;width*=2)for(i=0;i<3;++i)for(k=0;k<5;++k){
        n=counts[k];value=values[i];memset(expected,0xcd,512);OK(api.write(destination,expected,512));
        if(width==1)OK(api.fill8(destination+32,(unsigned char)value,n));
        else if(width==2)OK(api.fill16(destination+32,(unsigned short)value,n));
        else OK(api.fill32(destination+32,value,n));
        for(j=0;j<n*width;++j)expected[32+j]=(unsigned char)(value>>(8*(j%width)));
        OK(verify(destination,expected));OK(verify(source,input));++cases;
    }
    INVALID(api.copy(destination+511,source,2));INVALID(api.copy(destination,source+511,2));
    INVALID(api.copy(source+1,source,16));INVALID(api.copy(source,source+1,16));INVALID(api.copy(source,source,1));
    INVALID(api.copy(destination,source,(size_t)-1));INVALID(api.copy(destination,0,0));
    INVALID(api.copy(unowned,source,0));INVALID(api.fill8(0,0,0));
    INVALID(api.fill8(unowned,0,0));INVALID(api.fill8(destination+511,0,2));
    INVALID(api.fill16(destination+1,0,1));INVALID(api.fill16(destination+1,0,0));
    INVALID(api.fill32(destination+2,0,1));INVALID(api.fill32(destination,0,(size_t)-1));
    INVALID(api.fill16(destination,0,((size_t)-1)/2+1));
    INVALID(api.copy(UINT64_MAX-1,source,4));INVALID(api.fill8(UINT64_MAX-1,0,4));
    OK(verify(destination,expected));OK(verify(source,input));
    OK(api.create(&other,0,0));OK(api.allocate(&foreign,512));
    OK(api.write(foreign,expected,512));INVALID(api.copy(foreign,source,1));INVALID(api.fill8(destination,0,1));
    OK(verify(foreign,expected));OK(api.set(context));INVALID(api.copy(destination,foreign,1));
    OK(verify(destination,expected));OK(verify(source,input));OK(api.set(other));OK(api.free(foreign));OK(api.destroy(other));
    OK(api.set(context));OK(api.free(source));INVALID(api.copy(destination,source,1));
    INVALID(api.fill32(source,0,1));OK(verify(destination,expected));OK(api.free(destination));OK(api.destroy(context));
    REQUIRE(api.copy(0,0,0)==201);
    printf("{\"status\":\"pass\",\"cases\":%u,\"checked_bytes\":%u,\"rejections\":%u}\n",cases,checked_bytes,rejections);
    return 0;
}
