#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <cwchar>
#include <limits>
#include "bootstrap_tables_abi.hpp"

static unsigned checks=0;
static void require(bool value) { if (!value) { std::fputs("table contract failed\n",stderr); std::exit(2); } ++checks; }

int wmain(int argc,wchar_t** argv) {
    require(argc==2);
    wchar_t full[32768],loaded[32768];
    auto length=GetFullPathNameW(argv[1],32768,full,nullptr);
    require(length>0 && length<32768 && std::wcscmp(full,argv[1])==0);
    require(GetModuleHandleW(full)==nullptr);
    HMODULE module=LoadLibraryExW(full,nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    require(module!=nullptr);
    auto loaded_length=GetModuleFileNameW(module,loaded,32768);
    require(loaded_length>0 && loaded_length<32768 && _wcsicmp(loaded,full)==0);
    using Get = int (WINAPI *)(std::uint32_t,const void**);
    using State = int (WINAPI *)(TableState*);
    auto get=reinterpret_cast<Get>(GetProcAddress(module,"ctTableGet"));
    auto state=reinterpret_cast<State>(GetProcAddress(module,"ctTableState"));
    require(get!=nullptr && state!=nullptr);
    TableState s{};require(state(&s)==0 && s.mask==0 && s.stopped==0 && s.reserved==0);
    const void *a=nullptr,*b=nullptr,*again=nullptr;
    require(get(0,&a)==0 && a!=nullptr);require(get(1,&b)==0 && b!=nullptr && b!=a);
    require(get(0,&again)==0 && again==a);
    require(get(99,&again)==1 && again==nullptr);require(get(0,nullptr)==1);require(state(nullptr)==1);
    const auto* ct=static_cast<const CudartTable*>(a);const auto* hooks=static_cast<const HooksTable*>(b);
    require(ct->byte_size==104 && hooks->byte_size==56);
    require(ct->hole3==0 && ct->hole5==0 && ct->hole9==0 && ct->hole10==0 && ct->hole11==0);
    require(hooks->hole1==0 && hooks->hole3==0 && hooks->hole4==0 && hooks->hole5==0);
    require(ct->module && ct->context && ct->primary && ct->module_ext1 && ct->opaque_void && ct->module_ext2 && ct->compiler && hooks->first && hooks->second);
    std::uint64_t mask=0;
    auto hit=[&](unsigned bit) { mask|=std::uint64_t{1}<<bit;require(state(&s)==0 && s.mask==mask && s.stopped==1 && s.reserved==0); };
    auto bad=reinterpret_cast<void*>(std::uintptr_t{0xBAD0});
    auto wrapper=reinterpret_cast<const FatbincWrapper*>(bad);auto header=reinterpret_cast<const FatbinHeader*>(bad);
    auto module_sentinel=reinterpret_cast<CUmodule>(std::uintptr_t{0xDEAD});CUmodule output=module_sentinel;
    require(ct->module(&output,wrapper)==801 && output==nullptr);hit(0);
    CUcontext ctx=reinterpret_cast<CUcontext>(std::uintptr_t{0xDEAD});
    require(ct->context(&ctx,-1)==801 && ctx==nullptr);hit(1);
    require(ct->primary(-1,UINT32_MAX)==801);hit(2);
    output=module_sentinel;require(ct->module_ext1(&output,wrapper,bad,bad,UINT32_MAX)==801 && output==nullptr);hit(3);
    ct->opaque_void(std::numeric_limits<std::size_t>::max());hit(4);
    output=module_sentinel;require(ct->module_ext2(header,&output,bad,bad,UINT32_MAX)==801 && output==nullptr);hit(5);
    require(ct->compiler()==801);hit(6);
    for (unsigned i=0;i<2;++i) {
        Hook f=i==0?hooks->first:hooks->second;
        void* value=bad;std::size_t count=std::numeric_limits<std::size_t>::max();
        f(&value,&count);require(value==nullptr && count==0);hit(7+i);
        count=99;f(nullptr,&count);require(count==0);
        value=bad;f(&value,nullptr);require(value==nullptr);
        f(nullptr,nullptr);
    }
    require(ct->module(nullptr,wrapper)==1);require(ct->context(nullptr,0)==1);
    require(ct->module_ext1(nullptr,wrapper,bad,bad,0)==1);require(ct->module_ext2(header,nullptr,bad,bad,0)==1);
    require(state(&s)==0 && s.mask==511 && s.stopped==1 && s.reserved==0);
    require(get(0,&again)==0 && again==a && ct->byte_size==104);
    require(get(1,&again)==0 && again==b && hooks->byte_size==56);
    require(FreeLibrary(module)!=0);require(GetModuleHandleW(full)==nullptr);
    std::printf("{\"scope\":\"typed_deny_direct\",\"checks\":%u,\"mask\":511,\"stopped\":true,\"loaded_same_file\":true,\"unloaded\":true,\"runtime_exposed\":false,\"application_supported\":false}\n",checks);
    return 0;
}
