"""Isolated shared-provider Runtime prefix, followed by reservation cleanup."""
import argparse
import ctypes as c
import os
from pathlib import Path
import sys
import traceback


if __name__=='__main__':
    try:
        if not sys.flags.isolated or not sys.flags.no_site:raise ValueError('isolated no-site process required')
        sys.path.append(str(Path(__file__).resolve().parent));sys.dont_write_bytecode=True
        from primary_runtime_observer import PrimaryOwner,PrimaryObserver
        from real_bootstrap_worker import main,context
        from run_primary_runtime import audit_build
        import json
        p=argparse.ArgumentParser();p.add_argument('mode',choices=('intervention','intervention12090'));p.add_argument('--build-manifest',type=Path,required=True);args=p.parse_args()
        manifest=args.build_manifest.resolve();audit_build(manifest.parent.parent,json.loads(manifest.read_bytes()))
        owner=None;provider=None;observer=None
        def factory(loaded,**kwargs):
            global owner,provider,observer
            provider=loaded;owner=PrimaryOwner(loaded,Path.cwd()/'nvcuda.dll')
            observer=PrimaryObserver(loaded,owner=owner,**kwargs);return observer
        def primary_state():
            f=provider.cuDevicePrimaryCtxGetState;f.argtypes=[c.c_int,c.POINTER(c.c_uint),c.POINTER(c.c_int)];f.restype=c.c_int
            flags=c.c_uint(99);active=c.c_int(-1);code=f(0,c.byref(flags),c.byref(active));return dict(code=code,flags=flags.value,active=active.value)
        def finish(mode,value):
            if value.get('runtime_unload')!=dict(free_succeeded=True,module_absent=True):raise ValueError('Runtime remains loaded')
            value['scope']='ct_primary_runtime_bridge';value['deny_before']=owner.initial;value['deny_prefix']=owner.prefix_state
            value['deny_after_runtime']=owner.state();value['native_before']=owner.native_initial
            value['native_prefix']=owner.native_prefix;value['native_after_runtime']=owner.native_state()
            value['state_failures']=observer.state_failures
            value['foreign_lookups']=observer.foreign_lookups
            value['primary_before_reset']=primary_state()
            reset=provider.cuDevicePrimaryCtxReset_v2;reset.argtypes=[c.c_int];reset.restype=c.c_int
            value['primary_reset_code']=reset(0);value['primary_after_reset']=primary_state();value['current_after_reset']=context(provider)
            # Provider owns tables AND public controls. Retain until process exit.
            return value
        sys.argv=[sys.argv[0],args.mode];code=main(observer_type=factory,result_hook=finish)
    except BaseException:
        traceback.print_exc(file=sys.stderr);code=1
    sys.stdout.flush();sys.stderr.flush();os._exit(code)
