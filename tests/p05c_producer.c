#include "p05c_plugin.h"
static CUcontext retained;

__declspec(dllexport) HMODULE producer_driver(void) { return GetModuleHandleW(L"nvcuda.dll"); }

__declspec(dllexport) int producer_open(const char *ptx,struct SharedResources *r,CUcontext *identity) {
    float left[257],right[257],output[321];unsigned int i,flags=9;CUcontext popped=NULL;
    REQUIRE(retained==NULL);
    OK(cuDevicePrimaryCtxRetain(&retained,0));*identity=retained;
    OK(cuCtxPushCurrent(retained));OK(cuCtxGetFlags(&flags));REQUIRE(flags==0);
    OK(cuDevicePrimaryCtxSetFlags(0,0));
    for(i=0;i<257;++i){left[i]=(float)i*0.25f;right[i]=-(float)i*0.125f;}
    for(i=0;i<321;++i)output[i]=-12345.25f;
    OK(cuMemAlloc(&r->a,sizeof(left)));OK(cuMemAlloc(&r->b,sizeof(right)));OK(cuMemAlloc(&r->c,sizeof(output)));
    OK(cuMemcpyHtoD(r->a,left,sizeof(left)));OK(cuMemcpyHtoD(r->b,right,sizeof(right)));
    OK(cuMemcpyHtoD(r->c,output,sizeof(output)));OK(cuModuleLoadData(&r->module,ptx));
    OK(cuModuleGetFunction(&r->function,r->module,"vector_add"));
    OK(cuCtxPopCurrent(&popped));REQUIRE(popped==retained);
    return 0;
}

__declspec(dllexport) int producer_close(void) {
    REQUIRE(retained!=NULL);OK(cuDevicePrimaryCtxRelease(0));retained=NULL;return 0;
}
