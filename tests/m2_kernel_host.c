/* Independent CUDA Driver ABI consumer; synthetic kernels and buffers only. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "ct_cuda.h"
struct API {
#define FIELD(name,args) PFN_##name name;
CT_DRIVER_FUNCTIONS(FIELD)
#undef FIELD
} f;
static int checks=0,cases=0;
static size_t results=0,guards=0;
#define CHECK(call,want) do{int got=(call);++checks;if(got!=(want)){fprintf(stderr,"failed %s: got %d expected %d\n",#call,got,(want));return 1;}}while(0)
#define REQUIRE(condition) do{++checks;if(!(condition)){fprintf(stderr,"failed %s\n",#condition);return 1;}}while(0)
static char *fixture(const wchar_t *root,const wchar_t *name){
    wchar_t path[1024];FILE *file=NULL;long size;char *data;
    if(_snwprintf_s(path,1024,_TRUNCATE,L"%ls/%ls",root,name)<0)return NULL;
    if(_wfopen_s(&file,path,L"rb")||!file)return NULL;
    if(fseek(file,0,SEEK_END)||(size=ftell(file))<0||size>262144){fclose(file);return NULL;}
    rewind(file);data=(char*)malloc((size_t)size+1);if(!data){fclose(file);return NULL;}
    if(fread(data,1,(size_t)size,file)!=(size_t)size){free(data);fclose(file);return NULL;}
    data[size]=0;fclose(file);return data;
}
static int run_case(const char *source,const char *entry,int mode,unsigned int width,unsigned int group){
    unsigned int i,j,k,n=mode==3?width*width:width;
    size_t bytes=(size_t)n*sizeof(float),outbytes=(size_t)(n+group)*sizeof(float);
    float *a=(float*)malloc(bytes),*b=(float*)malloc(bytes),*out=(float*)malloc(outbytes);
    float alpha=0.75f;CUdeviceptr da=0,db=0,dc=0,bad=0;CUmodule module=NULL;CUfunction kernel=NULL,stale=NULL;
    void *args[5];unsigned int grid=(n+group-1)/group;
    REQUIRE(a&&b&&out);
    for(i=0;i<n;++i){a[i]=((float)(i%257)-128.0f)*0.25f;b[i]=((float)((i*7)%193)-96.0f)*0.5f;out[i]=NAN;}
    for(i=n;i<n+group;++i)out[i]=-12345.25f;
    CHECK(f.cuModuleLoadData(&module,source),0);
    CHECK(f.cuModuleGetFunction(&kernel,module,entry),0);
    CHECK(f.cuModuleGetFunction(&stale,module,"missing_entry"),500);
    CHECK(f.cuMemAlloc_v2(&da,bytes),0);CHECK(f.cuMemAlloc_v2(&db,bytes),0);CHECK(f.cuMemAlloc_v2(&dc,outbytes),0);
    CHECK(f.cuMemcpyHtoD_v2(da,a,bytes),0);CHECK(f.cuMemcpyHtoD_v2(db,b,bytes),0);CHECK(f.cuMemcpyHtoD_v2(dc,out,outbytes),0);
    args[0]=&da;args[1]=&db;args[2]=&dc;args[3]=&width;args[4]=&alpha;
    if(mode==2||mode==5){args[1]=&dc;args[2]=&width;}
    CHECK(f.cuLaunchKernel(kernel,grid,1,1,group,1,1,0,NULL,args,NULL),0);
    CHECK(f.cuCtxSynchronize(),0);CHECK(f.cuMemcpyDtoH_v2(out,dc,outbytes),0);
    for(i=0;i<n;++i){float expected=0;
        if(mode==0)expected=a[i]+b[i];
        if(mode==1){volatile float product=alpha*a[i];expected=product+b[i];}
        if(mode==2)expected=a[i]<0?0:a[i];
        if(mode==3){unsigned int row=i/width,col=i%width;for(k=0;k<width;++k){volatile float product=a[row*width+k]*b[k*width+col];expected=expected+product;}}
        if(mode==4)expected=a[i]-b[i];
        if(mode==5)expected=a[i]<1?1:a[i];
        REQUIRE(isfinite(out[i])&&fabsf(out[i]-expected)<=1e-5f+1e-4f*fabsf(expected));++results;
    }
    for(j=n;j<n+group;++j){REQUIRE(out[j]==-12345.25f);++guards;}
    CHECK(f.cuLaunchKernel(kernel,0,1,1,group,1,1,0,NULL,args,NULL),1);
    CHECK(f.cuLaunchKernel(kernel,grid,0,1,group,1,1,0,NULL,args,NULL),1);
    CHECK(f.cuLaunchKernel(kernel,grid,1,1,group,1,1,1,NULL,args,NULL),801);
    CHECK(f.cuLaunchKernel(kernel,grid,1,1,group,1,1,0,(CUstream)1,args,NULL),801);
    CHECK(f.cuLaunchKernel(kernel,grid,1,1,group,1,1,0,NULL,args,args),801);
    args[0]=&bad;CHECK(f.cuLaunchKernel(kernel,grid,1,1,group,1,1,0,NULL,args,NULL),1);args[0]=&da;
    CHECK(f.cuMemFree_v2(da),0);CHECK(f.cuMemFree_v2(db),0);CHECK(f.cuMemFree_v2(dc),0);
    CHECK(f.cuModuleUnload(module),0);CHECK(f.cuModuleUnload(module),400);
    CHECK(f.cuLaunchKernel(kernel,grid,1,1,group,1,1,0,NULL,args,NULL),400);
    free(a);free(b);free(out);++cases;return 0;
}
int wmain(int argc,wchar_t **argv){
    HMODULE library;CUcontext context=NULL,other=NULL;CUmodule module=NULL;CUfunction function=NULL;
    char *add,*saxpy,*relu,*matrix,*renamed;unsigned int i,g;
    const unsigned int lengths[]={1,63,64,65,255,256,257,100003};
    if(argc!=3){fprintf(stderr,"expected absolute DLL path and fixture directory\n");return 2;}
    library=LoadLibraryExW(argv[1],NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    if(!library){fprintf(stderr,"CT DLL unavailable\n");return 2;}
#define LOAD(name,args) f.name=(PFN_##name)GetProcAddress(library,#name);if(!f.name){fprintf(stderr,"missing export %s\n",#name);return 2;}
    CT_DRIVER_FUNCTIONS(LOAD)
#undef LOAD
    add=fixture(argv[2],L"vector_add.ptx");saxpy=fixture(argv[2],L"saxpy.ptx");relu=fixture(argv[2],L"relu.ptx");matrix=fixture(argv[2],L"matmul.ptx");
    REQUIRE(add&&saxpy&&relu&&matrix);CHECK(f.cuInit(0),0);CHECK(f.cuCtxCreate_v2(&context,0,0),0);
    CHECK(f.cuModuleLoadData(&module,"invalid PTX"),218);REQUIRE(module==NULL);
    CHECK(f.cuModuleLoadData(NULL,add),1);CHECK(f.cuModuleLoadData(&module,NULL),1);
    for(g=64;g<=128;g*=2){for(i=0;i<8;++i){CHECK(run_case(add,"vector_add",0,lengths[i],g),0);CHECK(run_case(saxpy,"saxpy",1,lengths[i],g),0);CHECK(run_case(relu,"relu",2,lengths[i],g),0);}}
    CHECK(run_case(matrix,"matmul",3,3,64),0);CHECK(run_case(matrix,"matmul",3,8,64),0);CHECK(run_case(matrix,"matmul",3,17,128),0);
    renamed=(char*)malloc(strlen(add)+1);REQUIRE(renamed!=NULL);strcpy_s(renamed,strlen(add)+1,add);
    {char *entry=strstr(renamed,"vector_add");char *op=strstr(renamed,"add.rn.f32");REQUIRE(entry&&op);memcpy(entry,"other_name",10);memcpy(op,"sub.rn.f32",10);}
    CHECK(run_case(renamed,"other_name",4,257,64),0);free(renamed);
    renamed=(char*)malloc(strlen(relu)+1);REQUIRE(renamed!=NULL);strcpy_s(renamed,strlen(relu)+1,relu);
    {char *scan=renamed,*constant;while((constant=strstr(scan,"0f00000000"))!=NULL){memcpy(constant,"0f3f800000",10);scan=constant+10;}}
    CHECK(run_case(renamed,"relu",5,257,64),0);free(renamed);
    renamed=(char*)malloc(strlen(add)+1);REQUIRE(renamed!=NULL);strcpy_s(renamed,strlen(add)+1,add);
    {char *version=strstr(renamed,".version 7.0");char *modifier=strstr(renamed,"add.rn.f32");REQUIRE(version&&modifier);
     version[9]='8';CHECK(f.cuModuleLoadData(&module,renamed),801);REQUIRE(module==NULL);version[9]='7';
     memcpy(modifier,"add.rz.f32",10);CHECK(f.cuModuleLoadData(&module,renamed),801);REQUIRE(module==NULL);}
    free(renamed);
    CHECK(f.cuModuleLoadData(&module,add),0);CHECK(f.cuModuleGetFunction(&function,module,"vector_add"),0);
    CHECK(f.cuCtxCreate_v2(&other,0,0),0);CHECK(f.cuModuleUnload(module),400);
    CHECK(f.cuLaunchKernel(function,1,1,1,64,1,1,0,NULL,NULL,NULL),400);
    CHECK(f.cuCtxDestroy_v2(other),0);CHECK(f.cuCtxDestroy_v2(context),0);
    CHECK(f.cuCtxCreate_v2(&context,0,0),0);CHECK(f.cuModuleUnload(module),400);CHECK(f.cuCtxDestroy_v2(context),0);
    printf("{\"status\":\"pass\",\"stage\":\"M2-PTX-to-Intel\",\"kernels\":4,\"cases\":%d,\"checks\":%d,\"results\":%zu,\"guards\":%zu,\"renamed_arithmetic_variant\":true}\n",cases,checks,results,guards);
    free(add);free(saxpy);free(relu);free(matrix);FreeLibrary(library);return 0;
}
