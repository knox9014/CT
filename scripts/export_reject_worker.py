"""Explicit diagnostic-only public export rejection, isolated child entrypoint."""
import ctypes as c
import os
from pathlib import Path
import sys
import traceback


def contracts(observer,provider):
    from real_bootstrap_worker import contracts as original
    from export_reject_observer import IDS
    checks=original(observer,provider)
    def require(ok):
        nonlocal checks
        if not ok:raise ValueError('export contract mismatch')
        checks+=1
    lookup=observer.make_lookup(observer.real_lookup);observer.callbacks.append(lookup)
    text=c.create_string_buffer(b'cuGetExportTable')
    require(not lookup(provider._handle,c.cast(text,c.c_void_p)))
    out=c.c_void_p(123)
    require(observer.bindings[b'cuGetProcAddress'][0](b'cuGetExportTable',c.byref(out),3000,0)==500 and out.value is None)
    status=c.c_int(-1)
    require(observer.bindings[b'cuGetProcAddress_v2'][0](b'cuGetExportTable',c.byref(out),3000,0,c.byref(status))==0
            and status.value==0 and out.value==c.cast(observer.export_callback,c.c_void_p).value)
    callback=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_void_p),c.c_void_p)(out.value)
    self_pointer=c.c_void_p();status=c.c_int(-1)
    require(observer.bindings[b'cuGetProcAddress_v2'][0](b'cuGetProcAddress',c.byref(self_pointer),12000,0,c.byref(status))==0
            and status.value==0 and self_pointer.value==c.cast(observer.bindings[b'cuGetProcAddress_v2'][0],c.c_void_p).value)
    for uuid in IDS:
        buffer=c.create_string_buffer(bytes.fromhex(uuid));out=c.c_void_p(123)
        require(callback(c.byref(out),c.cast(buffer,c.c_void_p))==801)
        require(out.value is None)
    require(callback(None,c.cast(buffer,c.c_void_p))==1)
    out=c.c_void_p(123);require(callback(c.byref(out),None)==1);require(out.value is None)
    return checks


def label(mode,value):
    if mode=='contracts':value['scope']='ct_export_contract'
    elif mode in ('intervention','intervention12090'):value['scope']='ct_export_rejection'
    else:raise ValueError('explicit export experiment mode required')
    return value


if __name__=='__main__':
    try:
        if not sys.flags.isolated or not sys.flags.no_site:raise ValueError('isolated no-site startup required')
        sys.path.append(str(Path(__file__).resolve().parent));sys.dont_write_bytecode=True
        from real_bootstrap_worker import main
        from export_reject_observer import ExportRejectObserver
        code=main(observer_type=ExportRejectObserver,contract_function=contracts,result_hook=label)
    except BaseException:
        traceback.print_exc(file=sys.stderr);code=1
    sys.stdout.flush();sys.stderr.flush();os._exit(code)
