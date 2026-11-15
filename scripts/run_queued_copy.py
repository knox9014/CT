"""Queued Runtime copies: real nvcc data, cleanup/error ABI and omission controls."""
import json
from pathlib import Path
import secrets
import shutil
import subprocess
from run_host_allocations import build as build_host
from run_runtime_attribute import ROOT
from run_relaxed_nvcc import host_environment,command,digest,verify_files,compiler_args,prepare_bundle
from run_validation import source_fingerprint


def validate_kernel(value,seed):
    if (type(value) is not dict or set(value)!={'status','seed','results'} or value['status']!='pass'
            or type(value['seed']) is not int or value['seed']!=seed):return False
    rows=value['results']
    if type(rows) is not list or len(rows)!=3:return False
    for mode,row in enumerate(rows):
        if type(row) is not list or len(row)!=32:return False
        expected=[(((((seed+mode*31)*7919+i*1237)&0xffffffff)^0xa5a55a5a)+17)&0xffffffff for i in range(32)]
        if any(type(v) is not int for v in row) or row!=expected:return False
    return True


def validate_control(mode,value):
    if mode=='absent':return type(value) is dict and set(value)=={'status','error'} and value['status']=='pass' and type(value['error']) is int and value['error']==35
    return (mode=='rejected_copy' and type(value) is dict and set(value)=={'status','error','cleanup','context_preserved'}
            and value['status']=='pass' and type(value['error']) is int and value['error']==1
            and value['cleanup'] is True and value['context_preserved'] is True)


def build():
    host=build_host();folder=host.parent;fingerprint=source_fingerprint(ROOT)
    if json.loads(host.read_bytes())['source_fingerprint']!=fingerprint:raise ValueError('source differs')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder)
    cl=base['host']['tools']['cl.exe']['path'];commands={}
    def run(label,args):commands[label]=args;command(args,folder,env,label)
    shutil.copyfile(ROOT/'tests/fixtures/queued_copy_runtime.cu',folder/'queued.cu');(folder/'keep-queued').mkdir()
    cuda=[('queued.cu' if x=='vector.cu' else 'queued.exe' if x=='default.exe' else 'keep-queued' if x=='keep' else x)
          for x in compiler_args(folder,producer.parent,base['host'])];run('queued-cuda',cuda)
    run('async-consumer',[cl,'/nologo','/utf-8','/W4','/WX','/EHsc','/std:c++17','/I'+str(producer.parent/'toolkit/include'),
                         str(ROOT/'tests/runtime_async_native_abi.cpp'),'/Fe:async-abi.exe'])
    from check_compatibility_profile import expected_exports
    definition=folder/'copy-noop.def';definition.write_text('EXPORTS\n'+'\n'.join(expected_exports(ROOT))+'\n')
    run('copy-noop',[cl,'/nologo','/utf-8','/W4','/WX','/LD','/DNOOP_COPY',str(ROOT/'tests/host_memory_driver_proxy.c'),
                     '/Fe:copy-noop.dll','/link','/DEF:'+str(definition)])
    files={name:digest(folder/name) for name in ['ct_cuda.dll','ct_cudart.dll','queued.cu','queued.exe','async-abi.exe','host-noop.dll','copy-noop.dll']}
    controls=[]
    for mode in ('absent','rejected_copy'):
        bundle=folder/('async-'+mode);bundle.mkdir();shutil.copyfile(folder/'async-abi.exe',bundle/'async-abi.exe');shutil.copyfile(folder/'ct_cudart.dll',bundle/'cudart64_12.dll')
        if mode!='absent':shutil.copyfile(folder/'ct_cuda.dll',bundle/'nvcuda.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        result=subprocess.run([str(bundle/'async-abi.exe'),str(bundle/'cudart64_12.dll'),mode],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr);verify_files(bundle,pins)
        if result.returncode or result.stderr or not validate_control(mode,json.loads(result.stdout)):raise ValueError('async ABI failed: '+mode)
        controls.append(dict(mode=mode,exit_code=result.returncode,result=json.loads(result.stdout),files=pins,stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    runs=[]
    for mode in ('positive','positive','noop_launch','noop_copy'):
        seed=secrets.randbelow(1000000)+1
        provider=folder/('host-noop.dll' if mode=='noop_launch' else 'copy-noop.dll' if mode=='noop_copy' else 'ct_cuda.dll')
        bundle,_=prepare_bundle(folder/'queued.exe',provider,[],folder/'queued-runs',runtime_dll=folder/'ct_cudart.dll')
        if mode!='positive':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        result=subprocess.run([str(bundle/'queued.exe'),str(seed)],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr);verify_files(bundle,pins)
        if mode=='positive':
            if result.returncode or result.stderr or not validate_kernel(json.loads(result.stdout),seed):raise ValueError('queued numerical check failed')
        elif result.returncode!=42 or result.stdout or result.stderr:raise ValueError('queued omission control failed')
        runs.append(dict(mode=mode,seed=seed,exit_code=result.returncode,bundle=bundle.relative_to(folder).as_posix(),files=pins,
                         stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    verify_files(folder,files)
    if source_fingerprint(ROOT)!=fingerprint:raise ValueError('source changed')
    manifest=dict(scope='diagnostic_queued_copy',release_claim=False,source_fingerprint=fingerprint,
                  host_manifest_sha256=digest(host),commands=commands,files=files,controls=controls,runs=runs)
    path=folder/'queued-copy-manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n');return path

if __name__=='__main__':
    print(json.dumps(dict(status='pass',manifest=build().relative_to(ROOT).as_posix(),release_claim=False)))
