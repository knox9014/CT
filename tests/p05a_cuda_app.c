/* Independent ordinary CUDA Driver consumer; no CT loader or explicit DLL path. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include "ct_cuda.h"
#ifdef DYNAMIC_CUDA
struct API {
#define FIELD(name,args) PFN_##name name;
CT_DRIVER_FUNCTIONS(FIELD)
#undef FIELD
} api;
#define CALL(name) api.name
#else
#define CALL(name) name
#endif
#define REQUIRE(x) do { if (!(x)) { fprintf(stderr,"check failed at line %d\n",__LINE__); return 3; } } while (0)
#define OK(x) REQUIRE((x)==0)

struct Shared {
    CUcontext primary;
    CUdeviceptr output;
    HANDLE ready, finish;
};

static DWORD WINAPI consumer(void *argument) {
    struct Shared *s=(struct Shared*)argument;
    CUcontext context=NULL,observed=NULL;
    float output[321];
    unsigned int i;
    OK(CALL(cuCtxGetCurrent)(&observed)); REQUIRE(observed==NULL);
    OK(CALL(cuDevicePrimaryCtxRetain)(&context,0)); REQUIRE(context==s->primary);
    OK(CALL(cuCtxGetCurrent)(&observed)); REQUIRE(observed==NULL);
    OK(CALL(cuCtxSetCurrent)(context));
    REQUIRE(SetEvent(s->ready));
    REQUIRE(WaitForSingleObject(s->finish,30000)==WAIT_OBJECT_0);
    OK(CALL(cuMemcpyDtoH_v2)(output,s->output,sizeof(output)));
    for(i=0;i<257;++i) REQUIRE(output[i]==(float)i*0.125f);
    for(i=257;i<321;++i) REQUIRE(output[i]==-12345.25f);
    OK(CALL(cuDevicePrimaryCtxRelease_v2)(0));
    observed=(CUcontext)(size_t)1;
    REQUIRE(CALL(cuCtxGetCurrent)(&observed)==709 && observed==NULL);
    OK(CALL(cuCtxSetCurrent)(NULL));
    OK(CALL(cuCtxGetCurrent)(&observed)); REQUIRE(observed==NULL);
    return 0;
}

int main(int argc,char **argv) {
    CUcontext ordinary=NULL,primary=NULL,other=NULL,observed=NULL,fresh=NULL;
    CUdeviceptr ordinary_memory=0,a=0,b=0,c=0;
    CUmodule module=NULL; CUfunction kernel=NULL;
    CUmodule stale_module; CUfunction stale_function;
    unsigned int flags=9,count=257,i; int active=9;
    unsigned int ordinary_value=0x1234abcd,ordinary_result=0;
    float left[257],right[257],output[321]; void *arguments[4];
    FILE *file=NULL; char *ptx; long length;
    struct Shared shared; HANDLE thread; DWORD thread_code;
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOOPENFILEERRORBOX);
    if(argc!=2) return 2;
#ifdef DYNAMIC_CUDA
    HMODULE driver=LoadLibraryW(L"nvcuda.dll");
    if(!driver) return 41;
#define RESOLVE(name,args) api.name=(PFN_##name)GetProcAddress(driver,#name);if(!api.name)return 42;
    CT_DRIVER_FUNCTIONS(RESOLVE)
#undef RESOLVE
#endif
    REQUIRE(CALL(cuDevicePrimaryCtxRetain)(&primary,0)==3);
    REQUIRE(CALL(cuDevicePrimaryCtxGetState)(0,&flags,&active)==3);
    REQUIRE(CALL(cuDevicePrimaryCtxRelease_v2)(0)==3);
    OK(CALL(cuInit)(0));
    REQUIRE(CALL(cuDevicePrimaryCtxRetain)(NULL,0)==1);
    primary=(CUcontext)(size_t)1;
    REQUIRE(CALL(cuDevicePrimaryCtxRetain)(&primary,-1)==101 && primary==NULL);
    REQUIRE(CALL(cuDevicePrimaryCtxGetState)(-1,&flags,&active)==101);
    REQUIRE(CALL(cuDevicePrimaryCtxGetState)(0,NULL,&active)==1);
    REQUIRE(CALL(cuDevicePrimaryCtxGetState)(0,&flags,NULL)==1);
    REQUIRE(CALL(cuDevicePrimaryCtxRelease_v2)(-1)==101);
    REQUIRE(CALL(cuDevicePrimaryCtxRelease_v2)(0)==201);
    OK(CALL(cuDevicePrimaryCtxGetState)(0,&flags,&active)); REQUIRE(flags==0 && active==0);
    OK(CALL(cuCtxGetCurrent)(&observed)); REQUIRE(observed==NULL);
    OK(CALL(cuCtxCreate_v2)(&ordinary,0,0));
    OK(CALL(cuMemAlloc_v2)(&ordinary_memory,sizeof(ordinary_value)));
    OK(CALL(cuMemcpyHtoD_v2)(ordinary_memory,&ordinary_value,sizeof(ordinary_value)));
    OK(CALL(cuDevicePrimaryCtxRetain)(&primary,0));
    OK(CALL(cuDevicePrimaryCtxRetain)(&other,0)); REQUIRE(primary==other && primary!=ordinary);
    OK(CALL(cuCtxGetCurrent)(&observed)); REQUIRE(observed==ordinary);
    OK(CALL(cuDevicePrimaryCtxGetState)(0,&flags,&active)); REQUIRE(flags==0 && active==1);
    OK(CALL(cuCtxPushCurrent_v2)(primary));
    REQUIRE(CALL(cuCtxDestroy_v2)(primary)==201);
    OK(CALL(cuCtxGetCurrent)(&observed)); REQUIRE(observed==primary);
    OK(CALL(cuMemAlloc_v2)(&a,sizeof(left))); OK(CALL(cuMemAlloc_v2)(&b,sizeof(right)));
    OK(CALL(cuMemAlloc_v2)(&c,sizeof(output)));
    for(i=0;i<257;++i) { left[i]=(float)i*0.25f; right[i]=-(float)i*0.125f; }
    for(i=0;i<321;++i) output[i]=-12345.25f;
    OK(CALL(cuMemcpyHtoD_v2)(a,left,sizeof(left))); OK(CALL(cuMemcpyHtoD_v2)(b,right,sizeof(right)));
    OK(CALL(cuMemcpyHtoD_v2)(c,output,sizeof(output)));
    REQUIRE(!fopen_s(&file,argv[1],"rb") && file);
    REQUIRE(!fseek(file,0,SEEK_END) && (length=ftell(file))>=0 && length<=262144);
    rewind(file); ptx=(char*)malloc((size_t)length+1); REQUIRE(ptx!=NULL);
    REQUIRE(fread(ptx,1,(size_t)length,file)==(size_t)length); fclose(file); ptx[length]=0;
    OK(CALL(cuModuleLoadData)(&module,ptx)); free(ptx);
    OK(CALL(cuModuleGetFunction)(&kernel,module,"vector_add"));
    shared.primary=primary; shared.output=c;
    shared.ready=CreateEventW(NULL,TRUE,FALSE,NULL); shared.finish=CreateEventW(NULL,TRUE,FALSE,NULL);
    REQUIRE(shared.ready && shared.finish);
    thread=CreateThread(NULL,0,consumer,&shared,0,NULL); REQUIRE(thread!=NULL);
    REQUIRE(WaitForSingleObject(shared.ready,30000)==WAIT_OBJECT_0);
    OK(CALL(cuDevicePrimaryCtxRelease_v2)(0)); OK(CALL(cuDevicePrimaryCtxRelease_v2)(0));
    OK(CALL(cuDevicePrimaryCtxGetState)(0,&flags,&active)); REQUIRE(active==1);
    OK(CALL(cuCtxGetCurrent)(&observed)); REQUIRE(observed==primary);
    arguments[0]=&a; arguments[1]=&b; arguments[2]=&c; arguments[3]=&count;
    OK(CALL(cuLaunchKernel)(kernel,5,1,1,64,1,1,0,NULL,arguments,NULL));
    OK(CALL(cuMemcpyDtoH_v2)(output,c,sizeof(output)));
    for(i=0;i<257;++i) REQUIRE(output[i]==left[i]+right[i]);
    for(i=257;i<321;++i) REQUIRE(output[i]==-12345.25f);
    REQUIRE(SetEvent(shared.finish));
    REQUIRE(WaitForSingleObject(thread,30000)==WAIT_OBJECT_0);
    REQUIRE(GetExitCodeThread(thread,&thread_code) && thread_code==0);
    CloseHandle(thread); CloseHandle(shared.ready); CloseHandle(shared.finish);
    OK(CALL(cuDevicePrimaryCtxGetState)(0,&flags,&active)); REQUIRE(active==0);
    REQUIRE(CALL(cuDevicePrimaryCtxRelease_v2)(0)==201);
    observed=(CUcontext)(size_t)1;
    REQUIRE(CALL(cuCtxGetCurrent)(&observed)==709 && observed==NULL);
    REQUIRE(CALL(cuCtxSynchronize)()==709);
    stale_module=(CUmodule)(size_t)1; stale_function=(CUfunction)(size_t)1;
    REQUIRE(CALL(cuModuleLoadData)(&stale_module,NULL)==709 && stale_module==NULL);
    REQUIRE(CALL(cuModuleGetFunction)(&stale_function,module,"vector_add")==709 && stale_function==NULL);
    REQUIRE(CALL(cuCtxPushCurrent_v2)(primary)==709);
    OK(CALL(cuCtxSetCurrent)(NULL));
    OK(CALL(cuCtxGetCurrent)(&observed)); REQUIRE(observed==ordinary);
    OK(CALL(cuMemcpyDtoH_v2)(&ordinary_result,ordinary_memory,sizeof(ordinary_result)));
    REQUIRE(ordinary_result==ordinary_value);
    REQUIRE(CALL(cuMemFree_v2)(a)==1);
    REQUIRE(CALL(cuModuleUnload)(module)==400);
    REQUIRE(CALL(cuLaunchKernel)(kernel,5,1,1,64,1,1,0,NULL,arguments,NULL)==400);
    OK(CALL(cuDevicePrimaryCtxRetain)(&fresh,0)); REQUIRE(fresh!=primary && fresh!=ordinary);
    OK(CALL(cuCtxPushCurrent_v2)(fresh));
    REQUIRE(CALL(cuModuleGetFunction)(&kernel,module,"vector_add")==400);
    OK(CALL(cuDevicePrimaryCtxRelease_v2)(0)); OK(CALL(cuCtxSetCurrent)(NULL));
    OK(CALL(cuMemFree_v2)(ordinary_memory)); OK(CALL(cuCtxDestroy_v2)(ordinary));
    puts("{\"status\":\"pass\",\"threads\":2,\"results\":514,\"guards\":128,\"primary_lifecycle\":true}");
    return 0;
}
