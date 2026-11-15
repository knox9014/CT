"""Actual native host allocation, optional-extension controls and prior kernel regressions."""
import json
from pathlib import Path
import shutil
import secrets
import subprocess
from run_owned_streams import build as build_streams
from run_runtime_attribute import CORE,ROOT
from run_relaxed_nvcc import host_environment,command,digest,verify_files,compiler_args,prepare_bundle
from run_owned_streams import validate_result as validate_kernel
from run_validation import source_fingerprint


def validate_result(mode,value):
    if type(value) is not dict or value.get('status')!='pass':return False
    if mode=='positive':
        return (set(value)=={'status','checked_bytes','host_allocations','guards'}
                and type(value['checked_bytes']) is int and value['checked_bytes']==1028
                and type(value['host_allocations']) is int and value['host_allocations']==2
                and value['guards'] is True)
    return (mode in ('missing_alloc','missing_free','forwarded_alloc','forwarded_free','absent')
            and set(value)=={'status','error'} and type(value['error']) is int and value['error']==35)


def build():
    streams=build_streams();folder=streams.parent;fingerprint=source_fingerprint(ROOT)
    if json.loads(streams.read_bytes())['source_fingerprint']!=fingerprint:raise ValueError('source differs')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder)
    cl=base['host']['tools']['cl.exe']['path'];commands={}
    def run(label,args):commands[label]=args;command(args,folder,env,label)
    include=str(producer.parent/'toolkit/include')
    run('host-consumer',[cl,'/nologo','/utf-8','/W4','/WX','/EHsc','/std:c++17','/I'+include,
                        str(ROOT/'tests/runtime_host_native_abi.cpp'),'/Fe:host.exe'])
    # Compare the complete47 Driver declarations against original pinned typedefs.
    abi=[]
    for role in ('reference','declared'):
        name='cuda_'+role+'_abi'
        run(name,[cl,'/nologo','/utf-8','/W4','/WX','/EHsc','/std:c++17','/I'+include,
                  str(ROOT/'tests'/(name+'.cpp')),'/Fe:'+name+'.exe'])
        result=subprocess.run([str(folder/(name+'.exe'))],cwd=folder,capture_output=True,timeout=30)
        if result.returncode or result.stderr:raise ValueError('Driver ABI probe failed')
        (folder/(name+'.stdout')).write_bytes(result.stdout);abi.append(result.stdout)
    if abi[0]!=abi[1] or sum(line.startswith(b'cu') for line in abi[0].splitlines())!=47:raise ValueError('Driver ABI differs')
    foreign=folder/'host_foreign.c'
    foreign.write_text('__declspec(dllexport) int __stdcall cuMemHostAlloc(void **p,unsigned long long n,unsigned f){(void)p;(void)n;(void)f;return 999;}\n__declspec(dllexport) int __stdcall cuMemFreeHost(void *p){(void)p;return 999;}')
    run('host-foreign',[cl,'/nologo','/W4','/WX','/LD',str(foreign),'/Fe:host_foreign.dll'])
    for mode in ('missing_alloc','missing_free','forwarded_alloc','forwarded_free'):
        absent='cuMemHostAlloc' if mode.endswith('alloc') else 'cuMemFreeHost'
        symbols=CORE+['cuMemHostAlloc','cuMemFreeHost']
        symbols=[s for s in symbols if s!=absent]
        if mode.startswith('forwarded'):symbols += [absent+'=host_foreign.'+absent]
        definition=folder/(mode+'.def');definition.write_text('EXPORTS\n'+'\n'.join(symbols)+'\n')
        args=[cl,'/nologo','/utf-8','/W4','/WX','/LD',str(ROOT/'tests/host_memory_driver_proxy.c'),'/Fe:host-'+mode+'.dll']
        if mode.startswith('forwarded'):args += ['/D'+absent+'=ct_hidden_'+absent,str(folder/'host_foreign.lib')]
        args += ['/link','/DEF:'+str(definition)];run('host-'+mode,args)
    shutil.copyfile(ROOT/'tests/fixtures/host_streams_runtime.cu',folder/'host-vector.cu')
    (folder/'keep-host').mkdir()
    cuda=[('host-vector.cu' if x=='vector.cu' else 'host-kernel.exe' if x=='default.exe' else 'keep-host' if x=='keep' else x)
          for x in compiler_args(folder,producer.parent,base['host'])]
    run('host-nvcc',cuda)
    from check_compatibility_profile import expected_exports
    definition=folder/'host-noop.def';definition.write_text('EXPORTS\n'+'\n'.join(expected_exports(ROOT))+'\n')
    run('host-noop',[cl,'/nologo','/utf-8','/W4','/WX','/LD','/DNOOP_LAUNCH',
        str(ROOT/'tests/host_memory_driver_proxy.c'),'/Fe:host-noop.dll','/link','/DEF:'+str(definition)])
    names=['host.exe','ct_cuda.dll','ct_cudart.dll','host_foreign.dll','host-kernel.exe','host-vector.cu','host-noop.dll']+['host-'+mode+'.dll' for mode in ('missing_alloc','missing_free','forwarded_alloc','forwarded_free')]
    files={name:digest(folder/name) for name in names};runs=[]
    for mode in ('positive','missing_alloc','missing_free','forwarded_alloc','forwarded_free','absent'):
        bundle=folder/('host-'+mode);bundle.mkdir();shutil.copyfile(folder/'host.exe',bundle/'host.exe');shutil.copyfile(folder/'ct_cudart.dll',bundle/'cudart64_12.dll')
        if mode!='absent':shutil.copyfile(folder/('ct_cuda.dll' if mode=='positive' else 'host-'+mode+'.dll'),bundle/'nvcuda.dll')
        if mode not in ('positive','absent'):shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        if mode.startswith('forwarded'):shutil.copyfile(folder/'host_foreign.dll',bundle/'host_foreign.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        result=subprocess.run([str(bundle/'host.exe'),str(bundle/'cudart64_12.dll'),mode],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr);verify_files(bundle,pins)
        if result.returncode or result.stderr:raise ValueError('native host case failed: '+mode)
        value=json.loads(result.stdout)
        if not validate_result(mode,value):raise ValueError('native host result failed')
        runs.append(dict(mode=mode,result=value,exit_code=0,files=pins,stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    nvcc_runs=[]
    for mode in ('positive','positive','noop'):
        seed=secrets.randbelow(1000000)+1
        bundle,_=prepare_bundle(folder/'host-kernel.exe',folder/('host-noop.dll' if mode=='noop' else 'ct_cuda.dll'),[],folder/'host-kernel-runs',runtime_dll=folder/'ct_cudart.dll')
        if mode=='noop':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        result=subprocess.run([str(bundle/'host-kernel.exe'),str(seed)],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.bin').write_bytes(result.stdout);(bundle/'stderr.bin').write_bytes(result.stderr);verify_files(bundle,pins)
        if mode=='positive':
            if result.returncode or result.stderr or not validate_kernel(json.loads(result.stdout),seed):raise ValueError('nvcc host kernel failed')
        elif result.returncode!=42 or result.stdout or result.stderr:raise ValueError('host no-op failed')
        nvcc_runs.append(dict(mode=mode,seed=seed,exit_code=result.returncode,bundle=bundle.relative_to(folder).as_posix(),files=pins,
                              stdout_sha256=digest(bundle/'stdout.bin'),stderr_sha256=digest(bundle/'stderr.bin')))
    verify_files(folder,files)
    if source_fingerprint(ROOT)!=fingerprint:raise ValueError('source changed')
    manifest=dict(scope='diagnostic_host_allocation',release_claim=False,source_fingerprint=fingerprint,
                  streams_manifest_sha256=digest(streams),commands=commands,files=files,runs=runs,nvcc_runs=nvcc_runs)
    path=folder/'host-manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n');return path

if __name__=='__main__':
    print(json.dumps(dict(status='pass',manifest=build().relative_to(ROOT).as_posix(),release_claim=False)))
