#include "p05c_plugin.h"
#include <stdlib.h>
#include <wchar.h>
struct HostAPI {
    PFN_cuInit init;PFN_cuDevicePrimaryCtxSetFlags set_flags;
    PFN_cuDevicePrimaryCtxGetState state;PFN_cuCtxGetFlags flags;
    PFN_cuCtxCreate_v3020 create;PFN_cuCtxDestroy destroy;
    PFN_cuCtxGetCurrent current;PFN_cuCtxSetCurrent set_current;PFN_cuCtxPushCurrent push;
    PFN_cuDevicePrimaryCtxReset reset;PFN_cuModuleUnload unload;
} api;

static HMODULE load_local(const wchar_t *name) {
    wchar_t path[32768],*slash;DWORD length=GetModuleFileNameW(NULL,path,32768);
    if(!length || length>=32768)return NULL;
    slash=wcsrchr(path,L'\\');if(!slash)return NULL;slash[1]=0;
    if(wcslen(path)+wcslen(name)>=32768)return NULL;
    if(wcscat_s(path,32768,name))return NULL;
    return LoadLibraryExW(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
}

static int check_flags(int expected_active,CUcontext expected_current) {
    unsigned int f,observed=9;int active=-1;CUcontext current=NULL;
    for(f=0;f<64;++f) {
        unsigned int schedule=f&7;int malformed=(f&~31U)!=0 || (schedule!=0&&schedule!=1&&schedule!=2&&schedule!=4);
        int expected=malformed?1:(f?801:0);
        REQUIRE(api.set_flags(0,f)==expected);
        OK(api.state(0,&observed,&active));REQUIRE(observed==0 && active==expected_active);
        OK(api.current(&current));REQUIRE(current==expected_current);
    }
    REQUIRE(api.set_flags(0,0xffffffff)==1);return 0;
}

int main(int argc,char **argv) {
    HMODULE driver,producer,consumer;ProducerOpen produce;ConsumerOpen consume;
    ConsumerRun run;PluginClose close_producer,close_consumer;PluginDriver producer_driver,consumer_driver;
    CUcontext ordinary=NULL,a=NULL,b=NULL,current=NULL,fresh=NULL;
    struct SharedResources resources,new_resources;unsigned int flags=9;int active;
    FILE *file=NULL;char *ptx;long length;
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOOPENFILEERRORBOX);if(argc!=2)return 2;
    driver=load_local(L"nvcuda.dll");if(!driver)return 41;
#define LOAD(field,type,name) api.field=(type)GetProcAddress(driver,name);if(!api.field)return 42
    LOAD(init,PFN_cuInit,"cuInit");LOAD(set_flags,PFN_cuDevicePrimaryCtxSetFlags,"cuDevicePrimaryCtxSetFlags_v2");
    LOAD(flags,PFN_cuCtxGetFlags,"cuCtxGetFlags");LOAD(state,PFN_cuDevicePrimaryCtxGetState,"cuDevicePrimaryCtxGetState");
    LOAD(create,PFN_cuCtxCreate_v3020,"cuCtxCreate_v2");LOAD(destroy,PFN_cuCtxDestroy,"cuCtxDestroy_v2");
    LOAD(current,PFN_cuCtxGetCurrent,"cuCtxGetCurrent");LOAD(set_current,PFN_cuCtxSetCurrent,"cuCtxSetCurrent");
    LOAD(push,PFN_cuCtxPushCurrent,"cuCtxPushCurrent_v2");LOAD(reset,PFN_cuDevicePrimaryCtxReset,"cuDevicePrimaryCtxReset_v2");
    LOAD(unload,PFN_cuModuleUnload,"cuModuleUnload");
#undef LOAD
    REQUIRE(api.set_flags(0,0)==3);REQUIRE(api.flags(&flags)==3);OK(api.init(0));
    REQUIRE(api.set_flags(-1,0)==101);flags=9;REQUIRE(api.flags(&flags)==201 && flags==0);
    REQUIRE(api.flags(NULL)==1);OK(check_flags(0,NULL));OK(api.create(&ordinary,0,0));
    OK(api.flags(&flags));REQUIRE(flags==0);
    REQUIRE(!fopen_s(&file,argv[1],"rb") && file);
    REQUIRE(!fseek(file,0,SEEK_END) && (length=ftell(file))>=0 && length<=262144);
    rewind(file);ptx=(char*)malloc((size_t)length+1);REQUIRE(ptx!=NULL);
    REQUIRE(fread(ptx,1,(size_t)length,file)==(size_t)length);fclose(file);ptx[length]=0;
    producer=load_local(L"producer.dll");consumer=load_local(L"consumer.dll");REQUIRE(producer&&consumer);
#define PLUGIN(var,type,dll,name) var=(type)GetProcAddress(dll,name);REQUIRE(var!=NULL)
    PLUGIN(produce,ProducerOpen,producer,"producer_open");PLUGIN(close_producer,PluginClose,producer,"producer_close");
    PLUGIN(producer_driver,PluginDriver,producer,"producer_driver");
    PLUGIN(consume,ConsumerOpen,consumer,"consumer_open");PLUGIN(run,ConsumerRun,consumer,"consumer_run");
    PLUGIN(close_consumer,PluginClose,consumer,"consumer_close");PLUGIN(consumer_driver,PluginDriver,consumer,"consumer_driver");
    OK(produce(ptx,&resources,&a));OK(consume(&b));REQUIRE(a==b && a!=ordinary);
    REQUIRE(producer_driver()==driver && consumer_driver()==driver);
    OK(check_flags(1,ordinary));OK(run(&resources));
    OK(close_producer());REQUIRE(FreeLibrary(producer));
    REQUIRE(GetModuleHandleW(L"producer.dll")==NULL);
    OK(check_flags(1,ordinary));OK(run(&resources));
    OK(api.push(b));OK(api.flags(&flags));REQUIRE(flags==0);OK(close_consumer());
    flags=9;REQUIRE(api.flags(&flags)==709 && flags==0);
    OK(api.state(0,&flags,&active));REQUIRE(active==0);REQUIRE(FreeLibrary(consumer));
    REQUIRE(GetModuleHandleW(L"consumer.dll")==NULL);
    OK(api.set_current(NULL));OK(api.current(&current));REQUIRE(current==ordinary);
    REQUIRE(api.unload(resources.module)==400);
    producer=load_local(L"producer.dll");REQUIRE(producer!=NULL);
    PLUGIN(produce,ProducerOpen,producer,"producer_open");PLUGIN(close_producer,PluginClose,producer,"producer_close");
    OK(produce(ptx,&new_resources,&fresh));REQUIRE(fresh!=a);free(ptx);
    OK(api.push(fresh));REQUIRE(api.unload(resources.module)==400);
    OK(api.reset(0));flags=9;REQUIRE(api.flags(&flags)==709 && flags==0);
    OK(api.set_flags(0,0));OK(close_producer());REQUIRE(FreeLibrary(producer));
    OK(api.set_current(NULL));OK(check_flags(0,ordinary));OK(api.destroy(ordinary));
    puts("{\"status\":\"pass\",\"libraries\":2,\"results\":514,\"guards\":128,\"shared_driver\":true}");
    return 0;
}
