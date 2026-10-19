/* Independent consumer: NVIDIA headers only, no CT header or CT loading code. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <cuda.h>
#include <cudaTypedefs.h>

static PFN_cuGetProcAddress_v11030 old_query;
static PFN_cuGetProcAddress_v12000 new_query;
static unsigned int queries;
static int use_new;
static void *lookup(const char *name,int version) {
    void *p=NULL;CUresult code;CUdriverProcAddressQueryResult status=CU_GET_PROC_ADDRESS_SYMBOL_NOT_FOUND;
    ++queries;
    if(use_new)code=new_query(name,&p,version,CU_GET_PROC_ADDRESS_LEGACY_STREAM,&status);
    else {code=old_query(name,&p,version,CU_GET_PROC_ADDRESS_DEFAULT);status=p?CU_GET_PROC_ADDRESS_SUCCESS:CU_GET_PROC_ADDRESS_SYMBOL_NOT_FOUND;}
    if(code!=CUDA_SUCCESS||status!=CU_GET_PROC_ADDRESS_SUCCESS)return NULL;
    return p;
}
#define REQUIRE(value) do{if(!(value)){fputs("entrypoint check failed\n",stderr);return 3;}}while(0)
#define CHECK(call) REQUIRE((call)==CUDA_SUCCESS)
#define API_LIST(X) \
 X(Init,cuInit,2000) X(DeviceGet,cuDeviceGet,2000) X(Create,cuCtxCreate,3020) \
 X(Destroy,cuCtxDestroy,4000) X(Alloc,cuMemAlloc,3020) X(Free,cuMemFree,3020) \
 X(HtoD,cuMemcpyHtoD,3020) X(DtoH,cuMemcpyDtoH,3020) X(ModuleLoad,cuModuleLoadData,2000) \
 X(GetFunction,cuModuleGetFunction,2000) X(Unload,cuModuleUnload,2000) X(Launch,cuLaunchKernel,4000)
struct API {
#define FIELD(field,name,version) PFN_##name##_v##version field;
API_LIST(FIELD)
#undef FIELD
};
struct Entry {const char *name,*export_name;int version;};
static const struct Entry entries[]={
 {"cuInit","cuInit",2000},{"cuDriverGetVersion","cuDriverGetVersion",2020},
 {"cuDeviceGetCount","cuDeviceGetCount",2000},{"cuDeviceGet","cuDeviceGet",2000},
 {"cuDeviceGetName","cuDeviceGetName",2000},{"cuDeviceGetAttribute","cuDeviceGetAttribute",2000},
 {"cuCtxCreate","cuCtxCreate_v2",3020},{"cuCtxDestroy","cuCtxDestroy_v2",4000},
 {"cuCtxGetCurrent","cuCtxGetCurrent",4000},{"cuCtxSetCurrent","cuCtxSetCurrent",4000},
 {"cuCtxPushCurrent","cuCtxPushCurrent_v2",4000},{"cuCtxPopCurrent","cuCtxPopCurrent_v2",4000},
 {"cuCtxGetDevice","cuCtxGetDevice",2000},{"cuCtxSynchronize","cuCtxSynchronize",2000},
 {"cuMemAlloc","cuMemAlloc_v2",3020},{"cuMemFree","cuMemFree_v2",3020},
 {"cuMemcpyHtoD","cuMemcpyHtoD_v2",3020},{"cuMemcpyDtoH","cuMemcpyDtoH_v2",3020},
 {"cuGetErrorName","cuGetErrorName",6000},{"cuGetErrorString","cuGetErrorString",6000},
 {"cuModuleLoadData","cuModuleLoadData",2000},{"cuModuleGetFunction","cuModuleGetFunction",2000},
 {"cuModuleUnload","cuModuleUnload",2000},{"cuLaunchKernel","cuLaunchKernel",4000}
};

int main(int argc,char **argv) {
    HMODULE driver;struct API f;unsigned int i,n=257;void *p;
    CUdevice device;CUcontext context;CUdeviceptr a,b,c;CUmodule module;CUfunction kernel;
    float left[257],right[257],output[321];void *arguments[4];
    char *ptx;long length;FILE *file=NULL;
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOOPENFILEERRORBOX);
    if(argc!=3)return 2;use_new=strcmp(argv[2],"v2")==0;
    driver=LoadLibraryW(L"nvcuda.dll");if(!driver)return 41;
    old_query=(PFN_cuGetProcAddress_v11030)GetProcAddress(driver,"cuGetProcAddress");
    new_query=(PFN_cuGetProcAddress_v12000)GetProcAddress(driver,"cuGetProcAddress_v2");
    if(!old_query||!new_query)return 42;
    for(i=0;i<sizeof(entries)/sizeof(entries[0]);++i) {
        p=lookup(entries[i].name,entries[i].version);
        REQUIRE(p!=NULL&&p==(void*)GetProcAddress(driver,entries[i].export_name));
    }
    REQUIRE(lookup("cuGetProcAddress",11030)==(void*)old_query);
    REQUIRE(lookup("cuGetProcAddress",12000)==(void*)new_query);
    REQUIRE(lookup("cuCtxCreate",11040)==NULL);
    REQUIRE(lookup("cuMemAlloc",3010)==NULL);
#define RESOLVE(field,name,version) f.field=(PFN_##name##_v##version)lookup(#name,version);REQUIRE(f.field!=NULL);
    API_LIST(RESOLVE)
#undef RESOLVE
    REQUIRE(sizeof(CUdeviceptr)==8&&sizeof(CUdriverProcAddressQueryResult)==4);
    if(fopen_s(&file,argv[1],"rb")||!file)return 6;
    if(fseek(file,0,SEEK_END)||(length=ftell(file))<0||length>262144){fclose(file);return 6;}
    rewind(file);ptx=(char*)malloc((size_t)length+1);if(!ptx){fclose(file);return 6;}
    if(fread(ptx,1,(size_t)length,file)!=(size_t)length){fclose(file);free(ptx);return 6;}
    fclose(file);ptx[length]=0;
    CHECK(f.Init(0));CHECK(f.DeviceGet(&device,0));CHECK(f.Create(&context,0,device));
    CHECK(f.Alloc(&a,sizeof(left)));CHECK(f.Alloc(&b,sizeof(right)));CHECK(f.Alloc(&c,sizeof(output)));
    for(i=0;i<n;++i){left[i]=(float)i*0.25f;right[i]=-(float)i*0.125f;}
    for(i=0;i<321;++i)output[i]=-12345.25f;
    CHECK(f.HtoD(a,left,sizeof(left)));CHECK(f.HtoD(b,right,sizeof(right)));CHECK(f.HtoD(c,output,sizeof(output)));
    CHECK(f.ModuleLoad(&module,ptx));free(ptx);CHECK(f.GetFunction(&kernel,module,"vector_add"));
    arguments[0]=&a;arguments[1]=&b;arguments[2]=&c;arguments[3]=&n;
    CHECK(f.Launch(kernel,5,1,1,64,1,1,0,NULL,arguments,NULL));CHECK(f.DtoH(output,c,sizeof(output)));
    for(i=0;i<n;++i)REQUIRE(output[i]==left[i]+right[i]);
    for(i=n;i<321;++i)REQUIRE(output[i]==-12345.25f);
    CHECK(f.Unload(module));CHECK(f.Free(a));CHECK(f.Free(b));CHECK(f.Free(c));CHECK(f.Destroy(context));
    printf("{\"status\":\"pass\",\"resolver\":\"%s\",\"queries\":%u,\"results\":257,\"guards\":64}\n",use_new?"v2":"v1",queries);
    return 0;
}
