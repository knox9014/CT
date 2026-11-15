"""Isolated version/device-count native probes; no allocation or kernel API."""
import argparse
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace


def require_loaded(library,path):
    kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.GetModuleFileNameW.argtypes=[c.c_void_p,c.c_wchar_p,c.c_uint32]
    kernel.GetModuleFileNameW.restype=c.c_uint32
    buffer=c.create_unicode_buffer(32768)
    length=kernel.GetModuleFileNameW(library._handle,buffer,len(buffer))
    if not length or length>=len(buffer) or Path(buffer.value).resolve()!=path.resolve():
        raise ValueError('unexpected loaded module location')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--site',type=Path,required=True)
    parser.add_argument('--kind',choices=('cupy','native'),required=True)
    parser.add_argument('--operation',choices=('version','version_null','device_count'),required=True)
    parser.add_argument('--observe',action='store_true')
    args=parser.parse_args()
    if not sys.flags.isolated or not sys.flags.no_site:raise ValueError('isolated no-site startup required')
    site=args.site.resolve();bundle=Path.cwd()
    sys.path.extend([str(Path(__file__).resolve().parent),str(site)])
    sys.pycache_prefix=str(bundle/'pycache');sys.dont_write_bytecode=True
    keep=[os.add_dll_directory(str(bundle))]
    provider=c.WinDLL(str(bundle/'nvcuda.dll'));keep.append(provider)
    provider_sha=require_loaded(provider,bundle/'nvcuda.dll')
    runtime_sha=None;observer=None
    if args.kind=='cupy':
        if args.operation!='version':raise ValueError('CuPy mode is version-only')
        import cupy_backends.cuda.api.runtime as runtime
        import cupy_backends.cuda.api.driver as driver
        for module in (runtime,driver):
            if not Path(module.__file__).resolve().is_relative_to(site):raise ValueError('package import escape')
        modules=(runtime,driver)
    else:
        runtime=c.WinDLL(str(bundle/'cudart64_12.dll'));keep.append(runtime)
        runtime_sha=require_loaded(runtime,bundle/'cudart64_12.dll')
        modules=(SimpleNamespace(__file__=str(bundle/'cudart64_12.dll')),)
    if args.observe:
        from cupy_bootstrap_observer import Observer
        observer=Observer(provider);observer.install(modules,native_probe=args.kind=='native')
    try:
        if args.kind=='cupy':
            value=runtime.runtimeGetVersion();code=0
        else:
            function=runtime.cudaGetDeviceCount if args.operation=='device_count' else runtime.cudaRuntimeGetVersion
            function.argtypes=[c.POINTER(c.c_int)];function.restype=c.c_int
            output=c.c_int(-1)
            code=function(None if args.operation=='version_null' else c.byref(output))
            value=None if args.operation=='version_null' else output.value
    finally:
        if observer is not None:observer.restore()
    result=dict(code=code,value=value,trace=[] if observer is None else observer.trace,
                patches=0 if observer is None else len(observer.saved),restored=True if observer is None else observer.restored)
    print(json.dumps(dict(result=result,provider_sha256=provider_sha,runtime_sha256=runtime_sha)))


if __name__=='__main__':main()
