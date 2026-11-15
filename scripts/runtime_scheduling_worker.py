"""Isolated actual scheduling prefix or fresh strict attribute75 control."""
import argparse
import ctypes as c
import json
import os
from pathlib import Path
import sys
import traceback


def primary_state(provider):
    function=provider.cuDevicePrimaryCtxGetState;function.argtypes=[c.c_int,c.POINTER(c.c_uint),c.POINTER(c.c_int)];function.restype=c.c_int
    flags=c.c_uint(99);active=c.c_int(-1);code=function(0,c.byref(flags),c.byref(active))
    return dict(code=code,flags=flags.value,active=active.value)


if __name__=='__main__':
    try:
        if not sys.flags.isolated or not sys.flags.no_site:raise ValueError('isolated no-site startup required')
        sys.path.append(str(Path(__file__).resolve().parent));sys.dont_write_bytecode=True
        from runtime_scheduling_check import POLICY
        from primary_runtime_observer import PrimaryOwner
        from runtime_scheduling_observer import SchedulingObserver
        from real_bootstrap_worker import main,context,version
        from run_primary_runtime import audit_build
        from run_cupy_bootstrap import digest
        from runtime_bootstrap_worker import require_loaded
        p=argparse.ArgumentParser();p.add_argument('mode',choices=('intervention','intervention12090','strict-control'))
        p.add_argument('--build-manifest',type=Path,required=True);args=p.parse_args()
        ct_environment={key:value for key,value in os.environ.items() if key.upper().startswith('CT_')}
        wanted={} if args.mode=='strict-control' else {'CT_VIRTUAL_TARGET':POLICY}
        if ct_environment!=wanted:raise ValueError('unexpected target policy environment')
        manifest=args.build_manifest.resolve();build=json.loads(manifest.read_bytes());audit_build(manifest.parent.parent,build)
        if digest(Path.cwd()/'nvcuda.dll')!=build['files']['context-bridge/bridge.dll']:raise ValueError('provider copy drift')
        if args.mode=='strict-control':
            directory=os.add_dll_directory(str(Path.cwd()));provider=c.WinDLL(str(Path.cwd()/'nvcuda.dll'))
            provider_sha=require_loaded(provider,Path.cwd()/'nvcuda.dll')
            init=provider.cuInit;init.argtypes=[c.c_uint];init.restype=c.c_int;init_code=init(0)
            count=provider.cuDeviceGetCount;count.argtypes=[c.POINTER(c.c_int)];count.restype=c.c_int
            output=c.c_int(-1);count_code=count(c.byref(output));count_value=output.value
            attribute=provider.cuDeviceGetAttribute;attribute.argtypes=[c.POINTER(c.c_int),c.c_int,c.c_int];attribute.restype=c.c_int
            output=c.c_int(-7);attribute_code=attribute(c.byref(output),75,0)
            value=dict(scope='ct_virtual_metadata_strict_control',policy_env_absent=True,init_code=init_code,
                       provider_sha256=provider_sha,runtime_sha256=None,device_count=dict(code=count_code,value=count_value),
                       attribute=dict(attribute=75,ordinal=0,result=attribute_code,value=output.value),actual_version=version(provider),
                       primary_state=primary_state(provider),current=context(provider),application_supported=False,shipping_version_authorized=False)
            print(json.dumps(value));code=0
        else:
            owner=provider=observer=None
            def factory(loaded,**kwargs):
                global owner,provider,observer
                provider=loaded;owner=PrimaryOwner(loaded,Path.cwd()/'nvcuda.dll')
                observer=SchedulingObserver(loaded,owner=owner,**kwargs);return observer
            def finish(mode,value):
                if value.get('runtime_unload')!=dict(free_succeeded=True,module_absent=True):raise ValueError('Runtime remains loaded')
                value.update(scope='ct_scheduling_metadata_prefix',policy_mode=POLICY,policy_env_value=os.environ.get('CT_VIRTUAL_TARGET'),software_target_only=True,
                             deny_before=owner.initial,deny_prefix=owner.prefix_state,deny_after_runtime=owner.state(),
                             native_before=owner.native_initial,native_prefix=owner.native_prefix,native_after_runtime=owner.native_state(),
                             state_failures=observer.state_failures,foreign_lookups=observer.foreign_lookups,primary_before_reset=primary_state(provider))
                reset=provider.cuDevicePrimaryCtxReset_v2;reset.argtypes=[c.c_int];reset.restype=c.c_int
                value['primary_reset_code']=reset(0);value['primary_after_reset']=primary_state(provider);value['current_after_reset']=context(provider)
                total=provider.cuDeviceTotalMem_v2;total.argtypes=[c.POINTER(c.c_size_t),c.c_int];total.restype=c.c_int
                output=c.c_size_t();result=total(c.byref(output),0);value['memory_control']=dict(code=result,total_bytes=output.value)
                name=provider.cuDeviceGetName;name.argtypes=[c.POINTER(c.c_char),c.c_int,c.c_int];name.restype=c.c_int
                text=c.create_string_buffer(256);result=name(text,256,0);value['name_control']=dict(code=result,value=text.value.decode('utf-8'))
                boundaries=[row for row in value['prefix_trace'] if row.get('kind')=='scheduling_attribute_boundary']
                if len(boundaries)!=1:raise ValueError('one observed scheduling boundary required')
                attribute=provider.cuDeviceGetAttribute;attribute.argtypes=[c.POINTER(c.c_int),c.c_int,c.c_int];attribute.restype=c.c_int
                def control(requested):
                    output=c.c_int(-7);code=attribute(c.byref(output),requested,0)
                    return dict(attribute=requested,ordinal=0,result=code,value=output.value)
                value['scheduling_controls']=[control(a) for a in (15,40)]
                value['boundary_control']=control(boundaries[0]['attribute'])
                return value
            sys.argv=[sys.argv[0],args.mode];code=main(observer_type=factory,result_hook=finish)
    except BaseException:
        traceback.print_exc(file=sys.stderr);code=1
    sys.stdout.flush();sys.stderr.flush();os._exit(code)
