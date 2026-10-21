/* Official-header-only Driver consumer for nested destroy and cross-thread stale state. */
#include <windows.h>
#include <cudaTypedefs.h>
#include <stdio.h>
struct API {
    PFN_cuInit init;PFN_cuCtxCreate_v3020 create;PFN_cuCtxDestroy destroy;
    PFN_cuCtxPushCurrent push;PFN_cuCtxPopCurrent pop;PFN_cuCtxSetCurrent set;
    PFN_cuCtxGetCurrent current;PFN_cuCtxSynchronize sync;PFN_cuCtxGetFlags flags;
    PFN_cuMemAlloc allocate;PFN_cuMemcpyHtoD write;PFN_cuMemcpyDtoH read;PFN_cuMemFree free;
} api;
#define REQUIRE(x) do {if(!(x)){fprintf(stderr,"check failed at line %d\n",__LINE__);return 3;}}while(0)
#define OK(x) REQUIRE((x)==0)
struct Shared { CUcontext victim;HANDLE ready,destroyed; };
static DWORD WINAPI worker(void *argument) {
    struct Shared *shared=(struct Shared*)argument;CUcontext current=NULL;unsigned int flags=9;
    OK(api.current(&current));REQUIRE(current==NULL);OK(api.push(shared->victim));
    REQUIRE(SetEvent(shared->ready));REQUIRE(WaitForSingleObject(shared->destroyed,30000)==WAIT_OBJECT_0);
    REQUIRE(api.sync()==709);REQUIRE(api.flags(&flags)==709 && flags==0);
    current=(CUcontext)(size_t)1;REQUIRE(api.current(&current)==709 && current==NULL);
    OK(api.set(NULL));OK(api.current(&current));REQUIRE(current==NULL);return 0;
}
static int check_root(CUcontext root,CUdeviceptr memory,unsigned int expected) {
    CUcontext current=NULL;unsigned int observed=0;
    OK(api.current(&current));REQUIRE(current==root);OK(api.read(&observed,memory,sizeof(observed)));
    REQUIRE(observed==expected);return 0;
}
int main(void) {
    HMODULE driver;CUcontext root=NULL,victim=NULL,buried=NULL,top=NULL,current=NULL,popped=NULL;
    CUdeviceptr memory=0;unsigned int value=0x1234abcd;struct Shared shared;HANDLE thread;DWORD code;
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOOPENFILEERRORBOX);
    driver=LoadLibraryW(L"nvcuda.dll");if(!driver)return 41;
#define LOAD(field,type,name) api.field=(type)GetProcAddress(driver,name);if(!api.field)return 42
    LOAD(init,PFN_cuInit,"cuInit");LOAD(create,PFN_cuCtxCreate_v3020,"cuCtxCreate_v2");
    LOAD(destroy,PFN_cuCtxDestroy,"cuCtxDestroy_v2");LOAD(push,PFN_cuCtxPushCurrent,"cuCtxPushCurrent_v2");
    LOAD(pop,PFN_cuCtxPopCurrent,"cuCtxPopCurrent_v2");LOAD(set,PFN_cuCtxSetCurrent,"cuCtxSetCurrent");
    LOAD(current,PFN_cuCtxGetCurrent,"cuCtxGetCurrent");LOAD(sync,PFN_cuCtxSynchronize,"cuCtxSynchronize");
    LOAD(flags,PFN_cuCtxGetFlags,"cuCtxGetFlags");LOAD(allocate,PFN_cuMemAlloc,"cuMemAlloc_v2");
    LOAD(write,PFN_cuMemcpyHtoD,"cuMemcpyHtoD_v2");LOAD(read,PFN_cuMemcpyDtoH,"cuMemcpyDtoH_v2");
    LOAD(free,PFN_cuMemFree,"cuMemFree_v2");
#undef LOAD
    OK(api.init(0));OK(api.create(&root,0,0));OK(api.allocate(&memory,sizeof(value)));
    OK(api.write(memory,&value,sizeof(value)));
    OK(api.create(&victim,0,0));OK(api.push(victim));OK(api.destroy(victim));
    current=(CUcontext)(size_t)1;
    if(api.current(&current)!=709 || current!=NULL) {fputs("duplicate stack entry was removed\n",stderr);return 3;}
    REQUIRE(api.sync()==709);REQUIRE(api.push(victim)==709);OK(api.set(NULL));OK(check_root(root,memory,value));
    OK(api.create(&buried,0,0));OK(api.create(&top,0,0));OK(api.destroy(buried));
    OK(api.current(&current));REQUIRE(current==top);OK(api.pop(&popped));REQUIRE(popped==top);
    current=(CUcontext)(size_t)1;REQUIRE(api.current(&current)==709 && current==NULL);
    OK(api.set(NULL));OK(api.destroy(top));OK(check_root(root,memory,value));
    OK(api.create(&shared.victim,0,0));shared.ready=CreateEventW(NULL,TRUE,FALSE,NULL);
    shared.destroyed=CreateEventW(NULL,TRUE,FALSE,NULL);REQUIRE(shared.ready&&shared.destroyed);
    thread=CreateThread(NULL,0,worker,&shared,0,NULL);REQUIRE(thread!=NULL);
    REQUIRE(WaitForSingleObject(shared.ready,30000)==WAIT_OBJECT_0);OK(api.destroy(shared.victim));
    REQUIRE(SetEvent(shared.destroyed));REQUIRE(WaitForSingleObject(thread,30000)==WAIT_OBJECT_0);
    REQUIRE(GetExitCodeThread(thread,&code) && code==0);CloseHandle(thread);CloseHandle(shared.ready);CloseHandle(shared.destroyed);
    OK(check_root(root,memory,value));REQUIRE(api.set(shared.victim)==709);OK(api.current(&current));REQUIRE(current==root);
    OK(api.free(memory));OK(api.destroy(root));OK(api.current(&current));REQUIRE(current==NULL);
    puts("{\"status\":\"pass\",\"cases\":3,\"threads\":2,\"memory_checks\":3}");return 0;
}
