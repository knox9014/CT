"""Isolated R2 child. Explicit NumPy CPU control or unchanged CuPy consumer."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys


def workload(xp):
    x=xp.arange(64,dtype=xp.float32)/xp.float32(8)-xp.float32(4)
    return xp.maximum(x*xp.float32(1.5)+xp.float32(.25),xp.float32(0))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('cpu','prefix','observe','workload','observe_workload'))
    parser.add_argument('--site',type=Path,required=True)
    args=parser.parse_args()
    if not sys.flags.isolated or not sys.flags.no_site:raise ValueError('isolated no-site startup required')
    site=args.site.resolve()
    # Keep the standard library ahead of any third-party module of the same name.
    sys.path.extend([str(Path(__file__).resolve().parent),str(site)])
    sys.pycache_prefix=str(Path.cwd()/'pycache')
    sys.dont_write_bytecode=True
    def verify_import(module):
        if not Path(module.__file__).resolve().is_relative_to(site):raise ValueError('unexpected package import location')
    stage='import';observer=None;handles=[]
    try:
        if args.mode=='cpu':
            import numpy as np
            verify_import(np)
            words=workload(np).view(np.uint32).tolist()
            result=dict(status='cpu_pass',stage='complete',words=words)
        else:
            bundle=Path.cwd()
            handles.append(os.add_dll_directory(str(bundle)))
            provider=ctypes.WinDLL(str(bundle/'nvcuda.dll'));handles.append(provider)
            import cupy as cp
            verify_import(cp)
            if args.mode in ('observe','observe_workload'):
                import cupy_backends.cuda.api.runtime as runtime
                import cupy_backends.cuda.api.driver as driver
                verify_import(runtime);verify_import(driver)
                from cupy_bootstrap_observer import Observer
                observer=Observer(provider);observer.install((runtime,driver))
            if args.mode in ('workload','observe_workload'):
                stage='input_creation'
                y=workload(cp)
                stage='copy_to_host'
                import numpy as np
                result=dict(status='gpu_pass',stage='complete',words=cp.asnumpy(y).view(np.uint32).tolist())
            else:
                stage='device_count'
                count=cp.cuda.runtime.getDeviceCount()
                # Changed bootstrap behavior requires review before any launch.
                result=dict(status='unexpected_prefix_success',stage=stage,count=count)
    except Exception as exc:
        result=dict(status='blocked',stage=stage,error_type=type(exc).__name__,
                    error_code=int(exc.status) if hasattr(exc,'status') else None)
    finally:
        if observer is not None:observer.restore()
    if observer is not None:
        result.update(trace=observer.trace,patches=len(observer.saved),restored=observer.restored)
    print(json.dumps(result))
    return 0


if __name__=='__main__':raise SystemExit(main())
