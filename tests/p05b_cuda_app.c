/* Ordinary CUDA Driver consumer: coordinated reset across two host threads. */
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
#define REQUIRE(x) do { if (!(x)) { fprintf(stderr,"check failed at line %d\n",__LINE__); return 3; } } while(0)
#define OK(x) REQUIRE((x)==0)

struct Resources { CUmodule module; CUfunction function; CUdeviceptr a,b,c; };
struct Shared { CUcontext primary; HANDLE ready,reset_done; };

static int prepare(const char *ptx,struct Resources *r) {
    float left[257],right[257],output[321]; unsigned int i;
    for(i=0;i<257;++i) {left[i]=(float)i*0.25f;right[i]=-(float)i*0.125f;}
    for(i=0;i<321;++i) output[i]=-12345.25f;
    OK(CALL(cuMemAlloc_v2)(&r->a,sizeof(left))); OK(CALL(cuMemAlloc_v2)(&r->b,sizeof(right)));
    OK(CALL(cuMemAlloc_v2)(&r->c,sizeof(output)));
    OK(CALL(cuMemcpyHtoD_v2)(r->a,left,sizeof(left))); OK(CALL(cuMemcpyHtoD_v2)(r->b,right,sizeof(right)));
    OK(CALL(cuMemcpyHtoD_v2)(r->c,output,sizeof(output)));
    OK(CALL(cuModuleLoadData)(&r->module,ptx));
    OK(CALL(cuModuleGetFunction)(&r->function,r->module,"vector_add"));
    return 0;
}

static int execute(struct Resources *r) {
    unsigned int count=257,i; void *arguments[4]={&r->a,&r->b,&r->c,&count}; float output[321];
    OK(CALL(cuLaunchKernel)(r->function,5,1,1,64,1,1,0,NULL,arguments,NULL));
    OK(CALL(cuMemcpyDtoH_v2)(output,r->c,sizeof(output)));
    for(i=0;i<257;++i) REQUIRE(output[i]==(float)i*0.125f);
    for(i=257;i<321;++i) REQUIRE(output[i]==-12345.25f);
    return 0;
}

static DWORD WINAPI consumer(void *argument) {
    struct Shared *s=(struct Shared*)argument; CUcontext primary=NULL,current=NULL;
    unsigned int flags; int active;
    OK(CALL(cuDevicePrimaryCtxRetain)(&primary,0)); REQUIRE(primary==s->primary);
    OK(CALL(cuCtxGetCurrent)(&current)); REQUIRE(current==NULL);
    OK(CALL(cuCtxSetCurrent)(primary)); REQUIRE(SetEvent(s->ready));
    REQUIRE(WaitForSingleObject(s->reset_done,30000)==WAIT_OBJECT_0);
    current=(CUcontext)(size_t)1;
    REQUIRE(CALL(cuCtxGetCurrent)(&current)==709 && current==NULL);
    REQUIRE(CALL(cuCtxSynchronize)()==709);
    OK(CALL(cuDevicePrimaryCtxGetState)(0,&flags,&active)); REQUIRE(flags==0 && active==0);
    OK(CALL(cuDevicePrimaryCtxRelease_v2)(0));
    REQUIRE(CALL(cuCtxSynchronize)()==709);
    OK(CALL(cuCtxSetCurrent)(NULL));
    OK(CALL(cuCtxGetCurrent)(&current)); REQUIRE(current==NULL);
    return 0;
}

int main(int argc,char **argv) {
    CUcontext ordinary=NULL,primary=NULL,second=NULL,fresh=NULL,current=NULL;
    CUdeviceptr ordinary_memory=0; unsigned int value=0x1234abcd,result=0,flags=9; int active=9;
    CUmodule invalid_module; CUfunction invalid_function;
    struct Resources before,after; struct Shared shared;
    FILE *file=NULL; char *ptx; long length; HANDLE thread; DWORD exit_code;
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOOPENFILEERRORBOX);
    if(argc!=2) return 2;
#ifdef DYNAMIC_CUDA
    HMODULE driver=LoadLibraryW(L"nvcuda.dll"); if(!driver)return 41;
#define RESOLVE(name,args) api.name=(PFN_##name)GetProcAddress(driver,#name);if(!api.name)return 42;
    CT_DRIVER_FUNCTIONS(RESOLVE)
#undef RESOLVE
#endif
    REQUIRE(CALL(cuDevicePrimaryCtxReset_v2)(0)==3);
    OK(CALL(cuInit)(0)); REQUIRE(CALL(cuDevicePrimaryCtxReset_v2)(-1)==101);
    OK(CALL(cuDevicePrimaryCtxReset_v2)(0)); OK(CALL(cuDevicePrimaryCtxReset_v2)(0));
    REQUIRE(CALL(cuDevicePrimaryCtxRelease_v2)(0)==201);
    OK(CALL(cuDevicePrimaryCtxGetState)(0,&flags,&active)); REQUIRE(flags==0 && active==0);
    OK(CALL(cuCtxGetCurrent)(&current)); REQUIRE(current==NULL);
    REQUIRE(!fopen_s(&file,argv[1],"rb") && file);
    REQUIRE(!fseek(file,0,SEEK_END) && (length=ftell(file))>=0 && length<=262144);
    rewind(file);ptx=(char*)malloc((size_t)length+1); REQUIRE(ptx!=NULL);
    REQUIRE(fread(ptx,1,(size_t)length,file)==(size_t)length); fclose(file);ptx[length]=0;
    OK(CALL(cuCtxCreate_v2)(&ordinary,0,0));
    OK(CALL(cuMemAlloc_v2)(&ordinary_memory,sizeof(value)));
    OK(CALL(cuMemcpyHtoD_v2)(ordinary_memory,&value,sizeof(value)));
    OK(CALL(cuDevicePrimaryCtxRetain)(&primary,0)); OK(CALL(cuDevicePrimaryCtxRetain)(&second,0));
    REQUIRE(primary==second); OK(CALL(cuCtxPushCurrent_v2)(primary));
    OK(prepare(ptx,&before)); OK(execute(&before));
    shared.primary=primary;
    shared.ready=CreateEventW(NULL,TRUE,FALSE,NULL);shared.reset_done=CreateEventW(NULL,TRUE,FALSE,NULL);
    REQUIRE(shared.ready && shared.reset_done);
    thread=CreateThread(NULL,0,consumer,&shared,0,NULL); REQUIRE(thread!=NULL);
    REQUIRE(WaitForSingleObject(shared.ready,30000)==WAIT_OBJECT_0);
    OK(CALL(cuDevicePrimaryCtxReset_v2)(0)); OK(CALL(cuDevicePrimaryCtxReset_v2)(0));
    OK(CALL(cuDevicePrimaryCtxGetState)(0,&flags,&active)); REQUIRE(active==0);
    current=(CUcontext)(size_t)1;
    REQUIRE(CALL(cuCtxGetCurrent)(&current)==709 && current==NULL);
    REQUIRE(CALL(cuMemFree_v2)(before.a)==709);
    invalid_module=(CUmodule)(size_t)1;invalid_function=(CUfunction)(size_t)1;
    REQUIRE(CALL(cuModuleLoadData)(&invalid_module,NULL)==709 && invalid_module==NULL);
    REQUIRE(CALL(cuModuleGetFunction)(&invalid_function,before.module,"vector_add")==709 && invalid_function==NULL);
    REQUIRE(SetEvent(shared.reset_done));
    REQUIRE(WaitForSingleObject(thread,30000)==WAIT_OBJECT_0);
    REQUIRE(GetExitCodeThread(thread,&exit_code) && exit_code==0);
    CloseHandle(thread);CloseHandle(shared.ready);CloseHandle(shared.reset_done);
    OK(CALL(cuCtxSetCurrent)(NULL));
    OK(CALL(cuCtxGetCurrent)(&current)); REQUIRE(current==ordinary);
    OK(CALL(cuMemcpyDtoH_v2)(&result,ordinary_memory,sizeof(result))); REQUIRE(result==value);
    REQUIRE(CALL(cuModuleUnload)(before.module)==400);
    REQUIRE(CALL(cuMemFree_v2)(before.a)==1);
    OK(CALL(cuDevicePrimaryCtxRetain)(&fresh,0)); REQUIRE(fresh!=primary && fresh!=ordinary);
    OK(CALL(cuCtxGetCurrent)(&current)); REQUIRE(current==ordinary);
    OK(CALL(cuCtxPushCurrent_v2)(fresh));
    REQUIRE(CALL(cuCtxSetCurrent)(primary)==709);
    REQUIRE(CALL(cuModuleUnload)(before.module)==400);
    REQUIRE(CALL(cuLaunchKernel)(before.function,1,1,1,1,1,1,0,NULL,NULL,NULL)==400);
    OK(prepare(ptx,&after)); free(ptx);
    OK(CALL(cuDevicePrimaryCtxRelease_v2)(0)); OK(CALL(cuDevicePrimaryCtxRelease_v2)(0));
    OK(CALL(cuDevicePrimaryCtxGetState)(0,&flags,&active)); REQUIRE(active==1);
    OK(execute(&after));
    OK(CALL(cuDevicePrimaryCtxReset_v2)(0));
    OK(CALL(cuDevicePrimaryCtxGetState)(0,&flags,&active)); REQUIRE(active==0);
    OK(CALL(cuDevicePrimaryCtxRelease_v2)(0)); REQUIRE(CALL(cuDevicePrimaryCtxRelease_v2)(0)==201);
    OK(CALL(cuDevicePrimaryCtxReset_v2)(0)); OK(CALL(cuCtxSetCurrent)(NULL));
    OK(CALL(cuMemFree_v2)(ordinary_memory)); OK(CALL(cuCtxDestroy_v2)(ordinary));
    puts("{\"status\":\"pass\",\"threads\":2,\"results\":514,\"guards\":128,\"reset_preserves_usage\":true}");
    return 0;
}
