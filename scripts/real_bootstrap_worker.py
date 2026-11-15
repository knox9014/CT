"""Isolated real-provider enumeration diagnostic, never application qualification."""
import argparse
import ctypes as c
import json
import os
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace

def version(provider):
    f=provider.cuDriverGetVersion;f.argtypes=[c.POINTER(c.c_int)];f.restype=c.c_int
    output=c.c_int(-1);return dict(code=f(c.byref(output)),value=output.value)

def context(provider):
    f=provider.cuCtxGetCurrent;f.argtypes=[c.POINTER(c.c_void_p)];f.restype=c.c_int
    output=c.c_void_p();code=f(c.byref(output));return dict(code=code,is_null=output.value is None)

def direct(provider):
    init=provider.cuInit;init.argtypes=[c.c_uint];init.restype=c.c_int
    count=provider.cuDeviceGetCount;count.argtypes=[c.POINTER(c.c_int)];count.restype=c.c_int
    null_version=provider.cuDriverGetVersion(None)
    output=c.c_int(-1);before=count(c.byref(output));before_value=output.value
    before_null=count(None);invalid_init=init(1);code=init(0)
    if code!=0:return dict(init_code=code,null_version=null_version,before_code=before,before_value=before_value,before_null=before_null,invalid_init=invalid_init)
    output=c.c_int(-1);result=count(c.byref(output));null_after=count(None)
    name=provider.cuDeviceGetName;name.argtypes=[c.c_char_p,c.c_int,c.c_int];name.restype=c.c_int
    buffer=c.create_string_buffer(256);name_code=name(buffer,len(buffer),0)
    return dict(init_code=code,count_code=result,count=output.value,null_version=null_version,before_code=before,
                before_value=before_value,before_null=before_null,invalid_init=invalid_init,after_null=null_after,
                name_code=name_code,device_name=buffer.value.decode('utf-8',errors='replace'),context=context(provider))

def contracts(observer,provider):
    checks=0
    def require(ok):
        nonlocal checks
        if not ok:raise ValueError('guard/native contract mismatch')
        checks+=1
    lookup=observer.make_lookup(observer.real_lookup);observer.callbacks.append(lookup)
    resolver1=observer.bindings[b'cuGetProcAddress'][0]
    resolver2=observer.bindings[b'cuGetProcAddress_v2'][0]
    for route in ('lookup','v1','v2'):
        for symbol in (b'cuModuleLoadData',b'cuLaunchKernel'):
            output=c.c_void_p();status=c.c_int(-1)
            if route=='lookup':
                text=c.create_string_buffer(symbol);pointer=lookup(provider._handle,c.cast(text,c.c_void_p))
            elif route=='v1':
                require(resolver1(symbol,c.byref(output),12000,0)==0);pointer=output.value
            else:
                require(resolver2(symbol,c.byref(output),12000,0,c.byref(status))==0 and status.value==0);pointer=output.value
            require(bool(pointer))
            if symbol==b'cuModuleLoadData':
                f=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_void_p),c.c_void_p)(pointer)
                module=c.c_void_p(0xDEAD);require(f(c.byref(module),c.c_void_p(0xBAD0))==801 and module.value is None)
            else:
                f=c.WINFUNCTYPE(c.c_int,c.c_void_p,*([c.c_uint]*7),c.c_void_p,c.POINTER(c.c_void_p),c.POINTER(c.c_void_p))(pointer)
                bad=c.cast(c.c_void_p(0xBAD0),c.POINTER(c.c_void_p))
                require(f(c.c_void_p(0xBAD0),1,1,1,1,1,1,0,c.c_void_p(0xBAD0),bad,bad)==801)
    v=observer.bindings[b'cuDriverGetVersion'][0];require(v(None)==1)
    get_count=observer.bindings[b'cuDeviceGetCount'][0];output=c.c_int(-1)
    require(get_count(c.byref(output))==3 and output.value==-1);require(get_count(None)==3)
    require(observer.bindings[b'cuInit'][0](1)==1)
    return checks

def main(*,observer_type=None,contract_function=None,result_hook=None):
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('nominal','faithful','intervention','intervention12090','direct','contracts'));args=p.parse_args()
    if not sys.flags.isolated or not sys.flags.no_site:raise ValueError('isolated no-site startup required')
    sys.path.append(str(Path(__file__).resolve().parent));sys.pycache_prefix=str(Path.cwd()/'pycache');sys.dont_write_bytecode=True
    from runtime_bootstrap_worker import require_loaded
    from real_bootstrap_observer import GuardedObserver
    if observer_type is not None:GuardedObserver=observer_type
    bundle=Path.cwd();keep=[os.add_dll_directory(str(bundle))]
    provider=c.WinDLL(str(bundle/'nvcuda.dll'));keep.append(provider)
    provider_sha=require_loaded(provider,bundle/'nvcuda.dll');before=version(provider)
    observer=None;runtime=None;runtime_sha=None;unload=None;teardown=[];restore_error=None
    sample=12000 if args.mode=='intervention' else 12090 if args.mode=='intervention12090' else None
    scope={'nominal':'ct_nominal','faithful':'ct_guarded_observation','intervention':'ct_guarded_counterfactual','intervention12090':'ct_guarded_counterfactual','direct':'ct_direct','contracts':'ct_guard_contract'}[args.mode]
    if args.mode=='direct':
        result=direct(provider)
    elif args.mode=='contracts':
        observer=GuardedObserver(provider,contract_mode=True)
        try:result=dict(checks=(contract_function or contracts)(observer,provider))
        finally:observer.restore()
    else:
        runtime_path=bundle/'cudart64_12.dll';runtime=c.WinDLL(str(runtime_path));keep.append(runtime)
        runtime_sha=require_loaded(runtime,runtime_path)
        if args.mode!='nominal':
            observer=GuardedObserver(provider,sample=sample)
            observer.install((SimpleNamespace(__file__=str(runtime_path)),),native_probe=True)
        try:
            f=runtime.cudaGetDeviceCount;f.argtypes=[c.POINTER(c.c_int)];f.restype=c.c_int
            output=c.c_int(-1)
            try:result=dict(status='returned',code=f(c.byref(output)),value=output.value)
            except OSError:result=dict(status='native_fault',code=None,value=output.value)
        finally:
            prefix=list(observer.trace) if observer else []
            if observer:
                try:observer.restore()
                except (OSError,ValueError) as exc:restore_error=type(exc).__name__
            kernel=c.WinDLL('kernel32',use_last_error=True)
            kernel.FreeLibrary.argtypes=[c.c_void_p];kernel.FreeLibrary.restype=c.c_int
            kernel.GetModuleHandleW.argtypes=[c.c_wchar_p];kernel.GetModuleHandleW.restype=c.c_void_p
            freed=bool(kernel.FreeLibrary(runtime._handle));unload=dict(free_succeeded=freed,module_absent=not bool(kernel.GetModuleHandleW(str(runtime_path))))
            teardown=list(observer.trace[len(prefix):]) if observer else []
    if args.mode in ('direct','contracts'):prefix=list(observer.trace) if observer else []
    after=version(provider)
    value=dict(scope=scope,sample=sample,application_supported=False,shipping_version_authorized=False,provider_sha256=provider_sha,
               runtime_sha256=runtime_sha,actual_version_before=before,actual_version_after=after,result=result,
               prefix_trace=prefix,teardown_trace=teardown,guard_hits=[] if observer is None else observer.guard_hits,
               callback_failures=[] if observer is None else observer.callback_failures,restored=True if observer is None else observer.restored,
               blocked_callbacks=[] if observer is None else observer.blocked_callbacks,
               patches=0 if observer is None else len(observer.saved),runtime_unload=unload,restore_error=restore_error)
    value['context_after']=context(provider)
    if result_hook is not None:value=result_hook(args.mode,value)
    print(json.dumps(value));sys.stdout.flush()
    if restore_error or value['callback_failures'] or (args.mode!='contracts' and value['guard_hits']):return 42
    return 0

if __name__=='__main__':
    try:code=main()
    except BaseException:
        traceback.print_exc(file=sys.stderr);code=1
    sys.stdout.flush();sys.stderr.flush()
    # Preserve cached callback objects through the end of native process activity.
    os._exit(code)
