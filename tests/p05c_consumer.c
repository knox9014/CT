#include "p05c_plugin.h"
static HMODULE driver;
static CUcontext retained;
static PFN_cuDevicePrimaryCtxRetain retain_context;
static PFN_cuDevicePrimaryCtxRelease release_context;
static PFN_cuCtxPushCurrent push;
static PFN_cuCtxPopCurrent pop;
static PFN_cuCtxGetFlags get_flags;
static PFN_cuLaunchKernel launch;
static PFN_cuMemcpyDtoH copy;
static PFN_cuMemcpyHtoD write_device;
static unsigned int executions;

__declspec(dllexport) HMODULE consumer_driver(void) { return driver; }

__declspec(dllexport) int consumer_open(CUcontext *identity) {
    REQUIRE(driver==NULL && retained==NULL);
    driver=LoadLibraryW(L"nvcuda.dll");REQUIRE(driver!=NULL);
#define LOAD(var,type,name) var=(type)GetProcAddress(driver,name);REQUIRE(var!=NULL)
    LOAD(retain_context,PFN_cuDevicePrimaryCtxRetain,"cuDevicePrimaryCtxRetain");
    LOAD(release_context,PFN_cuDevicePrimaryCtxRelease,"cuDevicePrimaryCtxRelease_v2");
    LOAD(push,PFN_cuCtxPushCurrent,"cuCtxPushCurrent_v2");
    LOAD(pop,PFN_cuCtxPopCurrent,"cuCtxPopCurrent_v2");
    LOAD(get_flags,PFN_cuCtxGetFlags,"cuCtxGetFlags");
    LOAD(launch,PFN_cuLaunchKernel,"cuLaunchKernel");LOAD(copy,PFN_cuMemcpyDtoH,"cuMemcpyDtoH_v2");
    LOAD(write_device,PFN_cuMemcpyHtoD,"cuMemcpyHtoD_v2");
#undef LOAD
    OK(retain_context(&retained,0));*identity=retained;return 0;
}

__declspec(dllexport) int consumer_run(const struct SharedResources *r) {
    CUcontext popped=NULL;unsigned int count=257,i,flags=9,generation=++executions;float output[321],left[257];
    CUdeviceptr a=r->a,b=r->b,c=r->c;void *arguments[4]={&a,&b,&c,&count};
    REQUIRE(retained!=NULL);OK(push(retained));OK(get_flags(&flags));REQUIRE(flags==0);
    for(i=0;i<257;++i)left[i]=(float)i*0.25f+(float)generation;
    for(i=0;i<321;++i)output[i]=-12345.25f;
    OK(write_device(a,left,sizeof(left)));OK(write_device(c,output,sizeof(output)));
#ifdef CT_TEST_SKIP_SECOND_LAUNCH
    /* Deliberately broken, separately built negative control; never the normative DLL. */
    if(executions==1) { OK(launch(r->function,5,1,1,64,1,1,0,NULL,arguments,NULL)); }
#else
    OK(launch(r->function,5,1,1,64,1,1,0,NULL,arguments,NULL));
#endif
    OK(copy(output,c,sizeof(output)));
    for(i=0;i<257;++i)if(output[i]!=(float)i*0.125f+(float)generation) {
        fprintf(stderr,"consumer output mismatch at execution %u\n",generation);return 3;
    }
    for(i=257;i<321;++i)REQUIRE(output[i]==-12345.25f);
    OK(pop(&popped));REQUIRE(popped==retained);return 0;
}

__declspec(dllexport) int consumer_close(void) {
    REQUIRE(retained!=NULL);OK(release_context(0));retained=NULL;
    REQUIRE(FreeLibrary(driver));driver=NULL;return 0;
}
