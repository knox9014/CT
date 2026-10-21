/* Official-header-only CT allocation metadata consumer. */
#include <windows.h>
#include <cudaTypedefs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
struct API {
    PFN_cuInit init;PFN_cuCtxCreate_v3020 create;PFN_cuCtxDestroy destroy;PFN_cuCtxSetCurrent set;
    PFN_cuMemAlloc allocate;PFN_cuMemFree free;PFN_cuMemcpyHtoD write;PFN_cuMemcpyDtoH read;
    PFN_cuMemGetAddressRange_v3020 range;PFN_cuPointerGetAttribute_v4000 attribute;
    PFN_cuGetProcAddress_v12000 query;PFN_cuDevicePrimaryCtxRetain retain;
    PFN_cuDevicePrimaryCtxRelease_v11000 release;PFN_cuDevicePrimaryCtxReset_v11000 reset;
} api;
static unsigned int metadata_queries,range_queries,checked_bytes;
#define REQUIRE(x) do {if(!(x)){fprintf(stderr,"metadata check failed at line %d: %s\n",__LINE__,#x);return 3;}}while(0)
#define OK(x) REQUIRE((x)==CUDA_SUCCESS)
struct Guard32 {unsigned int left,value,right;};
struct Guard64 {uint64_t left,value,right;};
static int metadata(CUdeviceptr pointer,CUdeviceptr base,size_t size) {
    struct Guard32 managed={0xabcdef12,99,0x1234abcd};struct Guard32 device=managed;
    struct Guard64 start={UINT64_MAX,0,UINT64_MAX},bytes=start;
    OK(api.attribute(&managed.value,CU_POINTER_ATTRIBUTE_IS_MANAGED,pointer));
    OK(api.attribute(&device.value,CU_POINTER_ATTRIBUTE_DEVICE_ORDINAL,pointer));
    OK(api.attribute(&start.value,CU_POINTER_ATTRIBUTE_RANGE_START_ADDR,pointer));
    OK(api.attribute(&bytes.value,CU_POINTER_ATTRIBUTE_RANGE_SIZE,pointer));
    REQUIRE(managed.value==0 && device.value==0 && start.value==base && bytes.value==size);
    REQUIRE(managed.left==0xabcdef12 && managed.right==0x1234abcd && device.left==managed.left && device.right==managed.right);
    REQUIRE(start.left==UINT64_MAX && start.right==UINT64_MAX && bytes.left==UINT64_MAX && bytes.right==UINT64_MAX);
    metadata_queries+=4;return 0;
}
static int range(CUdeviceptr pointer,CUdeviceptr expected,size_t size) {
    CUdeviceptr base=0;size_t bytes=0;OK(api.range(&base,&bytes,pointer));
    REQUIRE(base==expected && bytes==size);++range_queries;return 0;
}
int main(void) {
    HMODULE driver;CUcontext context=NULL,other=NULL,primary=NULL;CUdeviceptr pointer=0,base=0,foreign=0;
    size_t i,j,bytes=97;unsigned int sentinel;const size_t sizes[]={1,17,257,4097};
    driver=LoadLibraryW(L"nvcuda.dll");if(!driver)return 41;
#define LOAD(field,type,name) api.field=(type)GetProcAddress(driver,name);if(!api.field){fputs("missing query export\n",stderr);return 42;}
    LOAD(init,PFN_cuInit,"cuInit");LOAD(create,PFN_cuCtxCreate_v3020,"cuCtxCreate_v2");
    LOAD(destroy,PFN_cuCtxDestroy,"cuCtxDestroy_v2");LOAD(set,PFN_cuCtxSetCurrent,"cuCtxSetCurrent");
    LOAD(allocate,PFN_cuMemAlloc,"cuMemAlloc_v2");LOAD(free,PFN_cuMemFree,"cuMemFree_v2");
    LOAD(write,PFN_cuMemcpyHtoD,"cuMemcpyHtoD_v2");LOAD(read,PFN_cuMemcpyDtoH,"cuMemcpyDtoH_v2");
    LOAD(range,PFN_cuMemGetAddressRange_v3020,"cuMemGetAddressRange_v2");LOAD(attribute,PFN_cuPointerGetAttribute_v4000,"cuPointerGetAttribute");
    LOAD(query,PFN_cuGetProcAddress_v12000,"cuGetProcAddress_v2");LOAD(retain,PFN_cuDevicePrimaryCtxRetain,"cuDevicePrimaryCtxRetain");
    LOAD(release,PFN_cuDevicePrimaryCtxRelease_v11000,"cuDevicePrimaryCtxRelease_v2");LOAD(reset,PFN_cuDevicePrimaryCtxReset_v11000,"cuDevicePrimaryCtxReset_v2");
#undef LOAD
    sentinel=99;base=98;REQUIRE(api.range(&base,&bytes,0)==3 && base==98 && bytes==97);
    REQUIRE(api.attribute(&sentinel,CU_POINTER_ATTRIBUTE_IS_MANAGED,0)==3 && sentinel==99);
    OK(api.init(0));REQUIRE(api.range(NULL,NULL,0)==201);
    OK(api.create(&context,0,0));
    for(i=0;i<4;++i){
        unsigned char *input=(unsigned char*)malloc(sizes[i]),*output=(unsigned char*)malloc(sizes[i]);
        REQUIRE(input && output);for(j=0;j<sizes[i];++j)input[j]=(unsigned char)(j*13+i*7);
        memset(output,0xa5,sizes[i]);OK(api.allocate(&pointer,sizes[i]));OK(api.write(pointer,input,sizes[i]));
        OK(metadata(pointer,pointer,sizes[i]));OK(metadata(pointer+sizes[i]/2,pointer,sizes[i]));OK(metadata(pointer+sizes[i]-1,pointer,sizes[i]));
        OK(range(pointer,pointer,sizes[i]));OK(range(pointer+sizes[i]/2,pointer,sizes[i]));OK(range(pointer+sizes[i]-1,pointer,sizes[i]));
        base=0;OK(api.range(&base,NULL,pointer));REQUIRE(base==pointer);
        bytes=0;OK(api.range(NULL,&bytes,pointer));REQUIRE(bytes==sizes[i]);OK(api.range(NULL,NULL,pointer));range_queries+=3;
        sentinel=99;REQUIRE(api.attribute(&sentinel,CU_POINTER_ATTRIBUTE_IS_MANAGED,pointer+sizes[i])==1 && sentinel==99);
        base=98;bytes=97;REQUIRE(api.range(&base,&bytes,pointer+sizes[i])==500 && base==98 && bytes==97);
        for(j=1;j<=20;++j)if(j!=8 && j!=9 && j!=11 && j!=12){
            struct Guard64 guard={UINT64_MAX,UINT64_MAX,UINT64_MAX};
            REQUIRE(api.attribute(&guard.value,(CUpointer_attribute)j,pointer)==801);
            REQUIRE(guard.left==UINT64_MAX && guard.value==UINT64_MAX && guard.right==UINT64_MAX);
        }
        sentinel=99;REQUIRE(api.attribute(&sentinel,(CUpointer_attribute)0,pointer)==1 && sentinel==99);
        REQUIRE(api.attribute(&sentinel,(CUpointer_attribute)21,pointer)==1 && sentinel==99);
        REQUIRE(api.attribute(NULL,CU_POINTER_ATTRIBUTE_IS_MANAGED,pointer)==1);
        OK(api.read(output,pointer,sizes[i]));REQUIRE(memcmp(input,output,sizes[i])==0);checked_bytes+=(unsigned int)sizes[i];
        OK(api.free(pointer));sentinel=99;REQUIRE(api.attribute(&sentinel,CU_POINTER_ATTRIBUTE_IS_MANAGED,pointer)==1 && sentinel==99);
        REQUIRE(api.range(NULL,NULL,pointer)==500);free(input);free(output);
    }
    OK(api.allocate(&pointer,19));OK(api.create(&other,0,0));OK(api.allocate(&foreign,23));
    OK(metadata(pointer+18,pointer,19));OK(metadata(foreign+22,foreign,23));REQUIRE(api.range(NULL,NULL,pointer)==500);
    OK(api.set(NULL));OK(api.set(NULL));OK(metadata(pointer,pointer,19));REQUIRE(api.range(NULL,NULL,pointer)==201);
    OK(api.set(other));OK(api.free(foreign));OK(api.destroy(other));OK(api.set(context));
    OK(api.free(pointer));OK(api.destroy(context));
    OK(api.retain(&primary,0));OK(api.set(primary));OK(api.allocate(&pointer,29));OK(metadata(pointer+28,pointer,29));
    OK(api.reset(0));sentinel=99;REQUIRE(api.attribute(&sentinel,CU_POINTER_ATTRIBUTE_IS_MANAGED,pointer)==1 && sentinel==99);
    REQUIRE(api.range(NULL,NULL,pointer)==709);OK(api.set(NULL));OK(api.release(0));
    { const char *names[]={"cuMemGetAddressRange","cuPointerGetAttribute"};int floors[]={3020,4000};
      const char *symbols[]={"cuMemGetAddressRange_v2","cuPointerGetAttribute"};
      for(i=0;i<2;++i){void *function=NULL;CUdriverProcAddressQueryResult status;
        OK(api.query(names[i],&function,floors[i],0,&status));REQUIRE(function==(void*)GetProcAddress(driver,symbols[i]) && status==0);
        OK(api.query(names[i],&function,floors[i]-1,0,&status));REQUIRE(!function && status==2);
      }}
    printf("{\"status\":\"pass\",\"metadata_queries\":%u,\"range_queries\":%u,\"checked_bytes\":%u}\n",metadata_queries,range_queries,checked_bytes);return 0;
}
