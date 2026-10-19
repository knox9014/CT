/* Independent native ABI host. Inputs are synthetic, output has no private data. */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "ct_cuda.h"
struct API {
#define CT_FIELD(name,args) PFN_##name name;
    CT_DRIVER_FUNCTIONS(CT_FIELD)
#undef CT_FIELD
} f;
static int checks = 0;
#define CHECK(call,want) do { int got=(call); ++checks; if(got!=(want)) { \
    fprintf(stderr,"failed: %s returned %d, expected %d\n",#call,got,(want)); return 1; } } while(0)
#define REQUIRE(condition) do { ++checks; if(!(condition)) { fprintf(stderr,"failed: %s\n",#condition); return 1; } } while(0)
struct Worker { CUcontext context; int ok; };
static DWORD WINAPI worker(LPVOID raw) {
    struct Worker *w=(struct Worker*)raw;
    CUdeviceptr p=0;
    CUcontext current=(CUcontext)1;
    unsigned char input[4]={11,22,33,44}, output[4]={0};
    if(f.cuMemAlloc_v2(&p,4)!=201 || f.cuCtxGetCurrent(&current)!=0 || current!=NULL) return 1;
    if(f.cuCtxPushCurrent_v2(w->context)!=0 || f.cuMemAlloc_v2(&p,4)!=0) return 1;
    if(f.cuMemcpyHtoD_v2(p,input,4)!=0 || f.cuMemcpyDtoH_v2(output,p,4)!=0 || memcmp(input,output,4)) return 1;
    if(f.cuMemFree_v2(p)!=0 || f.cuCtxPopCurrent_v2(&current)!=0 || current!=w->context) return 1;
    w->ok=1;
    return 0;
}
int wmain(int argc,wchar_t **argv) {
    HMODULE library;
    int count=0, value=123;
    CUdevice device=-1;
    CUcontext a=NULL,b=NULL,current=NULL;
    CUdeviceptr p=0,remaining=0;
    unsigned char input[4096],output[4096];
    char name[256];
    const char *error=NULL;
    unsigned int i;
    HANDLE thread;
    DWORD code=1;
    struct Worker state;
    if(argc!=2) { fprintf(stderr,"expected absolute CT DLL path\n"); return 2; }
    library=LoadLibraryExW(argv[1],NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    if(!library) { fprintf(stderr,"CT DLL load failed\n"); return 2; }
#define CT_LOAD(name,args) f.name=(PFN_##name)GetProcAddress(library,#name); if(!f.name) { fprintf(stderr,"missing export: %s\n",#name); return 2; }
    CT_DRIVER_FUNCTIONS(CT_LOAD)
#undef CT_LOAD
    CHECK(f.cuDeviceGetCount(&count),3);
    CHECK(f.cuInit(1),1); CHECK(f.cuInit(0),0); CHECK(f.cuInit(0),0);
    CHECK(f.cuDeviceGetCount(&count),0); REQUIRE(count>0);
    CHECK(f.cuDeviceGet(NULL,0),1); CHECK(f.cuDeviceGet(&device,-1),101);
    CHECK(f.cuDeviceGet(&device,0),0);
    CHECK(f.cuDeviceGetName(name,sizeof(name),device),0); REQUIRE(strstr(name,"B390")!=NULL);
    CHECK(f.cuDeviceGetName(name,1,device),0); REQUIRE(name[0]==0);
    CHECK(f.cuDeviceGetName(name,0,device),1);
    CHECK(f.cuDeviceGetAttribute(&value,1,device),0); REQUIRE(value>=128);
    CHECK(f.cuDeviceGetAttribute(&value,75,device),801); REQUIRE(value==0);
    CHECK(f.cuDriverGetVersion(&value),801); REQUIRE(value==0);
    CHECK(f.cuMemAlloc_v2(&p,16),201);
    CHECK(f.cuCtxCreate_v2(&a,0,device),0); CHECK(f.cuCtxGetCurrent(&current),0); REQUIRE(current==a);
    CHECK(f.cuCtxGetDevice(&value),0); REQUIRE(value==device);
    CHECK(f.cuCtxCreate_v2(NULL,0,device),1);
    CHECK(f.cuMemAlloc_v2(&p,0),1); CHECK(f.cuMemAlloc_v2(NULL,16),1);
    CHECK(f.cuMemAlloc_v2(&p,sizeof(input)),0); REQUIRE(p!=0);
    for(i=0;i<sizeof(input);++i) input[i]=(unsigned char)(i*17+3);
    memset(output,0,sizeof(output));
    CHECK(f.cuMemcpyHtoD_v2(p,input,sizeof(input)),0);
    CHECK(f.cuMemcpyDtoH_v2(output,p,sizeof(output)),0); REQUIRE(memcmp(input,output,sizeof(input))==0);
    memset(output,0,sizeof(output));
    CHECK(f.cuMemcpyDtoH_v2(output,p+17,101),0); REQUIRE(memcmp(output,input+17,101)==0);
    CHECK(f.cuMemcpyHtoD_v2(p+17,input+101,101),0);
    CHECK(f.cuMemcpyDtoH_v2(output,p+17,101),0); REQUIRE(memcmp(output,input+101,101)==0);
    CHECK(f.cuMemcpyHtoD_v2(p,NULL,0),0); CHECK(f.cuMemcpyDtoH_v2(NULL,p,0),0);
    CHECK(f.cuMemcpyDtoH_v2(output,p+4090,7),1);
    CHECK(f.cuMemcpyDtoH_v2(output,~(CUdeviceptr)0-2,8),1);
    CHECK(f.cuMemcpyHtoD_v2(p,NULL,1),1); CHECK(f.cuMemcpyDtoH_v2(NULL,p,1),1);
    CHECK(f.cuMemFree_v2(p+1),1);
    CHECK(f.cuCtxCreate_v2(&b,0,device),0);
    CHECK(f.cuMemcpyDtoH_v2(output,p,4),1); CHECK(f.cuMemFree_v2(p),1);
    CHECK(f.cuCtxPopCurrent_v2(&current),0); REQUIRE(current==b);
    CHECK(f.cuCtxGetCurrent(&current),0); REQUIRE(current==a);
    state.context=a; state.ok=0;
    thread=CreateThread(NULL,0,worker,&state,0,NULL); REQUIRE(thread!=NULL);
    REQUIRE(WaitForSingleObject(thread,30000)==WAIT_OBJECT_0);
    REQUIRE(GetExitCodeThread(thread,&code)!=0); CloseHandle(thread); REQUIRE(code==0 && state.ok==1);
    CHECK(f.cuCtxGetCurrent(&current),0); REQUIRE(current==a);
    CHECK(f.cuCtxSetCurrent(NULL),0); CHECK(f.cuCtxGetCurrent(&current),0); REQUIRE(current==NULL);
    CHECK(f.cuMemAlloc_v2(&remaining,16),201); CHECK(f.cuCtxSetCurrent(a),0);
    CHECK(f.cuCtxDestroy_v2(b),0); CHECK(f.cuCtxDestroy_v2(b),201);
    CHECK(f.cuCtxPushCurrent_v2(b),201);
    CHECK(f.cuCtxSynchronize(),0); CHECK(f.cuMemFree_v2(p),0);
    CHECK(f.cuMemFree_v2(p),1); CHECK(f.cuMemcpyDtoH_v2(output,p,4),1);
    CHECK(f.cuMemAlloc_v2(&remaining,32),0); CHECK(f.cuCtxDestroy_v2(a),0);
    CHECK(f.cuCtxGetCurrent(&current),0); REQUIRE(current==NULL);
    CHECK(f.cuMemAlloc_v2(&p,4),201);
    for(i=0;i<32;++i) {
        CHECK(f.cuCtxCreate_v2(&a,0,device),0); CHECK(f.cuMemAlloc_v2(&p,16),0);
        CHECK(f.cuMemFree_v2(p),0); CHECK(f.cuCtxDestroy_v2(a),0);
    }
    CHECK(f.cuGetErrorName(801,&error),0); REQUIRE(strcmp(error,"CUDA_ERROR_NOT_SUPPORTED")==0);
    CHECK(f.cuGetErrorString(201,&error),0); REQUIRE(error!=NULL && strlen(error)>0);
    CHECK(f.cuGetErrorName(-1,&error),1); CHECK(f.cuGetErrorName(0,NULL),1);
    printf("{\"status\":\"pass\",\"stage\":\"M1-driver-memory\",\"checks\":%d,\"threads\":2,\"context_cycles\":32,\"ptx_execution\":false}\n",checks);
    FreeLibrary(library);
    return 0;
}
