"""Isolated strict-policy Runtime metadata prefix and public post-run controls."""
import argparse
import ctypes as c
import json
import os
from pathlib import Path
import sys
import traceback


if __name__=='__main__':
    try:
        if not sys.flags.isolated or not sys.flags.no_site:raise ValueError('isolated no-site process required')
        if any(k.upper().startswith('CT_') for k in os.environ):raise ValueError('strict default environment required')
        sys.path.append(str(Path(__file__).resolve().parent));sys.dont_write_bytecode=True
        from primary_runtime_observer import PrimaryOwner
        from runtime_metadata_observer import MetadataObserver
        from real_bootstrap_worker import main,context
        from run_primary_runtime import audit_build
        from run_cupy_bootstrap import digest
        p=argparse.ArgumentParser();p.add_argument('mode',choices=('intervention','intervention12090'));p.add_argument('--build-manifest',type=Path,required=True);args=p.parse_args()
        manifest=args.build_manifest.resolve();build=json.loads(manifest.read_bytes());base=audit_build(manifest.parent.parent,build)
        if digest(Path.cwd()/'nvcuda.dll')!=build['files']['context-bridge/bridge.dll']:raise ValueError('copied shared provider differs')
        owner=None;provider=None;observer=None
        def factory(loaded,**kwargs):
            global owner,provider,observer
            provider=loaded;owner=PrimaryOwner(loaded,Path.cwd()/'nvcuda.dll');observer=MetadataObserver(loaded,owner=owner,**kwargs);return observer
        def primary_state():
            f=provider.cuDevicePrimaryCtxGetState;f.argtypes=[c.c_int,c.POINTER(c.c_uint),c.POINTER(c.c_int)];f.restype=c.c_int
            flags=c.c_uint(99);active=c.c_int(-1);code=f(0,c.byref(flags),c.byref(active));return dict(code=code,flags=flags.value,active=active.value)
        def finish(mode,value):
            if value.get('runtime_unload')!=dict(free_succeeded=True,module_absent=True):raise ValueError('Runtime remains loaded')
            value.update(scope='ct_runtime_metadata_prefix',policy_mode='strict-default',policy_env_absent=True,
                         deny_before=owner.initial,deny_prefix=owner.prefix_state,deny_after_runtime=owner.state(),
                         native_before=owner.native_initial,native_prefix=owner.native_prefix,native_after_runtime=owner.native_state(),
                         state_failures=observer.state_failures,foreign_lookups=observer.foreign_lookups,primary_before_reset=primary_state())
            reset=provider.cuDevicePrimaryCtxReset_v2;reset.argtypes=[c.c_int];reset.restype=c.c_int
            value['primary_reset_code']=reset(0);value['primary_after_reset']=primary_state();value['current_after_reset']=context(provider)
            total=provider.cuDeviceTotalMem_v2;total.argtypes=[c.POINTER(c.c_size_t),c.c_int];total.restype=c.c_int
            output=c.c_size_t();code=total(c.byref(output),0);value['memory_control']=dict(code=code,total_bytes=output.value)
            name=provider.cuDeviceGetName;name.argtypes=[c.POINTER(c.c_char),c.c_int,c.c_int];name.restype=c.c_int
            text=c.create_string_buffer(256);code=name(text,256,0);value['name_control']=dict(code=code,value=text.value.decode('utf-8'))
            return value
        sys.argv=[sys.argv[0],args.mode];code=main(observer_type=factory,result_hook=finish)
    except BaseException:
        traceback.print_exc(file=sys.stderr);code=1
    sys.stdout.flush();sys.stderr.flush();os._exit(code)
