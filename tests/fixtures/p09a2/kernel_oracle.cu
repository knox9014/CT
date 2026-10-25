/* Report GPU readbacks; expected arithmetic lives only in the Python oracle. */
#include <cuda_runtime.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ct_cuda.h"
#define REQUIRE(x) do {if(!(x)){fprintf(stderr,"native contract line %d\n",__LINE__);return 42;}}while(0)
#define OK(x) REQUIRE((int)(x)==0)
extern "C" __global__ void ct_oracle_add(const unsigned *a,const unsigned *b,unsigned *c,unsigned n) {
    unsigned i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)c[i]=a[i]+b[i];
}
extern "C" __global__ void ct_oracle_bias(unsigned *c,unsigned n,unsigned bias) {
    unsigned i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)c[i]+=bias;
}
extern "C" void ct_run_a(const unsigned *,unsigned *,unsigned);
extern "C" void ct_run_b(const unsigned *,unsigned *,unsigned);
struct Result {unsigned seed,a[21],b[21],c[21];};
struct Gate {HANDLE go;volatile LONG ready;};
struct Work {Result *result;Gate *gate;int code;};
static int run_case(Result *r,int repeats,int modules,Gate *gate) {
    unsigned a[21],b[21],c[21],*da=0,*db=0,*dc=0;
    for(unsigned i=0;i<21;++i){a[i]=b[i]=0xdecafbad;c[i]=0xa5a5a5a5;}
    for(unsigned i=0;i<17;++i){a[i+2]=r->seed*13+i*37;b[i+2]=r->seed*17+i*19;}
    OK(cudaMalloc((void**)&da,sizeof(a)));OK(cudaMalloc((void**)&db,sizeof(b)));OK(cudaMalloc((void**)&dc,sizeof(c)));
    OK(cudaMemcpy(da,a,sizeof(a),cudaMemcpyHostToDevice));OK(cudaMemcpy(db,b,sizeof(b),cudaMemcpyHostToDevice));OK(cudaMemcpy(dc,c,sizeof(c),cudaMemcpyHostToDevice));
    if(gate){InterlockedIncrement(&gate->ready);REQUIRE(WaitForSingleObject(gate->go,30000)==WAIT_OBJECT_0);}
    for(int i=0;i<repeats;++i){
        if(modules){ct_run_a(da+2,dc+2,17);ct_run_b(dc+2,dc+2,17);}
        else {ct_oracle_add<<<2,16>>>(da+2,db+2,dc+2,17);ct_oracle_bias<<<2,16>>>(dc+2,17,7);}
        OK(cudaGetLastError());
    }
    OK(cudaDeviceSynchronize());
    OK(cudaMemcpy(r->a,da,sizeof(a),cudaMemcpyDeviceToHost));OK(cudaMemcpy(r->b,db,sizeof(b),cudaMemcpyDeviceToHost));OK(cudaMemcpy(r->c,dc,sizeof(c),cudaMemcpyDeviceToHost));
    OK(cudaFree(da));OK(cudaFree(db));OK(cudaFree(dc));return 0;
}
static DWORD WINAPI worker(void *argument){Work *w=(Work*)argument;w->code=run_case(w->result,1,0,w->gate);return (DWORD)w->code;}
static void array(const unsigned *p){putchar('[');for(int i=0;i<21;++i){if(i)putchar(',');printf("%u",p[i]);}putchar(']');}
int main(int argc,char **argv) {
    REQUIRE(argc==3);const char *mode=argv[1];unsigned seed=(unsigned)strtoul(argv[2],0,10);REQUIRE(seed>0&&seed<=1000000);
    int count=1;Result results[8]={};int errors[5]={};int error_count=0;
    int devices=0;OK(cudaGetDeviceCount(&devices));REQUIRE(devices>0);
    HMODULE driver=GetModuleHandleW(L"nvcuda.dll");REQUIRE(driver!=0);
    PFN_cuCtxCreate_v2 create=(PFN_cuCtxCreate_v2)GetProcAddress(driver,"cuCtxCreate_v2");
    PFN_cuCtxSetCurrent select=(PFN_cuCtxSetCurrent)GetProcAddress(driver,"cuCtxSetCurrent");
    PFN_cuCtxGetCurrent current=(PFN_cuCtxGetCurrent)GetProcAddress(driver,"cuCtxGetCurrent");
    PFN_cuCtxDestroy_v2 destroy=(PFN_cuCtxDestroy_v2)GetProcAddress(driver,"cuCtxDestroy_v2");
    REQUIRE(create&&select&&current&&destroy);
    if(!strcmp(mode,"boundaries")){
        void *args[4]={};
        errors[0]=(int)cudaLaunchKernel((const void*)ct_oracle_add,dim3(0,1,1),dim3(16,1,1),args,0,0);
        errors[1]=(int)cudaLaunchKernel((const void*)ct_oracle_add,dim3(1,1,1),dim3(1025,1,1),args,0,0);
        errors[2]=(int)cudaLaunchKernel((const void*)ct_oracle_add,dim3(2,1,1),dim3(16,1,1),args,1,0);
        errors[3]=(int)cudaLaunchKernel((const void*)ct_oracle_add,dim3(2,1,1),dim3(16,1,1),args,0,0);
        errors[4]=(int)cudaLaunchKernel((const void*)0,dim3(2,1,1),dim3(16,1,1),args,0,0);
        error_count=5;(void)cudaGetLastError();
    }
    if(!strcmp(mode,"parallel")){
        count=8;Gate gate={CreateEventW(0,TRUE,FALSE,0),0};REQUIRE(gate.go!=0);HANDLE threads[8]={};Work work[8]={};
        for(int i=0;i<8;++i){results[i].seed=seed+(unsigned)i;work[i].result=&results[i];work[i].gate=&gate;threads[i]=CreateThread(0,0,worker,&work[i],0,0);REQUIRE(threads[i]!=0);}
        ULONGLONG end=GetTickCount64()+30000;while(gate.ready<8&&GetTickCount64()<end)Sleep(1);
        SetEvent(gate.go);REQUIRE(WaitForMultipleObjects(8,threads,TRUE,60000)==WAIT_OBJECT_0);
        for(int i=0;i<8;++i){CloseHandle(threads[i]);REQUIRE(work[i].code==0);}CloseHandle(gate.go);
    } else if(!strcmp(mode,"two_contexts")) {
        count=3;CUcontext contexts[2]={};
        for(int i=0;i<2;++i){OK(create(&contexts[i],0,0));results[i].seed=seed+(unsigned)i;OK(run_case(&results[i],1,0,0));CUcontext observed=0;OK(current(&observed));REQUIRE(observed==contexts[i]);}
        OK(select(contexts[0]));results[2].seed=seed+2;OK(run_case(&results[2],1,0,0));
        OK(destroy(contexts[1]));OK(destroy(contexts[0]));
    } else {
        CUcontext ordinary=0;if(!strcmp(mode,"ordinary"))OK(create(&ordinary,0,0));
        results[0].seed=seed;OK(run_case(&results[0],!strcmp(mode,"repeat")?10:1,!strcmp(mode,"multi_module"),0));
        if(ordinary){CUcontext observed=0;OK(current(&observed));REQUIRE(observed==ordinary);OK(destroy(ordinary));}
    }
    printf("{\"seed\":%u,\"mode\":\"%s\",\"errors\":[",seed,mode);
    for(int i=0;i<error_count;++i){if(i)putchar(',');printf("%d",errors[i]);}printf("],\"runs\":[");
    for(int i=0;i<count;++i){if(i)putchar(',');printf("{\"seed\":%u,\"a\":",results[i].seed);array(results[i].a);printf(",\"b\":");array(results[i].b);printf(",\"c\":");array(results[i].c);putchar('}');}
    puts("]}");return 0;
}
