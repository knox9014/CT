"""Local official-header Runtime attribute ABI and loader controls; no release claim."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid
from run_relaxed_nvcc import command, host_environment, digest, verify_files
from run_validation import source_fingerprint
from cache_budget import ensure_budget,GIB

ROOT = Path(__file__).resolve().parents[1]
CORE = ['cuInit','cuDeviceGetCount','cuDeviceGet','cuCtxGetCurrent','cuCtxGetDevice',
        'cuCtxSetCurrent','cuDevicePrimaryCtxRetain','cuDevicePrimaryCtxRelease_v2',
        'cuCtxSynchronize','cuMemAlloc_v2','cuMemFree_v2','cuMemcpyHtoD_v2',
        'cuMemcpyDtoH_v2','cuMemcpyDtoD_v2','cuMemsetD8_v2']


def validate_result(mode, value):
    if mode in ('normal', 'minimal'):
        if type(value) is not dict or set(value) != {'status','values','context_unchanged'}:
            return False
        values = value['values']
        return (value['status'] == 'pass' and value['context_unchanged'] is True
                and type(values) is list and len(values) == 11
                and all(type(v) is int and v > 0 for v in values[:7])
                and type(values[7]) is int and 0 <= values[7] <= 16384
                and all(type(v) is int and v == 0 for v in values[8:]))
    return (mode in ('missing','forwarded','absent') and type(value) is dict
            and set(value) == {'status','loader_error'} and value['status'] == 'pass'
            and type(value['loader_error']) is int and value['loader_error'] == 35)


def build():
    ensure_budget(ROOT,GIB)
    folder = ROOT / '.cache/runtime-attribute-runs' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    fingerprint = source_fingerprint(ROOT)
    producer = ROOT / '.cache/p09a2-producer/manifest.json'
    base, env = host_environment(producer, folder)
    include = producer.parent / 'toolkit/include'
    cl = base['host']['tools']['cl.exe']['path']
    commands = {}
    def run(label, argv, environment=env, cwd=None):
        commands[label] = argv
        command(argv, folder, environment, label, cwd=cwd)
    for role, manifest, dll in [('driver','Cargo.toml','ct_cuda.dll'),
                                ('runtime','crates/ct-cudart/Cargo.toml','ct_cudart.dll')]:
        target = folder / 'target'
        argv = ['cargo','build','--manifest-path',manifest,'--target-dir',str(target)]
        if role == 'driver': argv += ['-p','ct-cuda']
        run(role, argv, dict(os.environ,CARGO_INCREMENTAL='0'), ROOT)
        shutil.copyfile(target / 'debug' / dll, folder / dll)
    run('consumer',[cl,'/nologo','/utf-8','/W4','/WX','/EHsc','/std:c++17',
         '/I'+str(include),str(ROOT/'tests/runtime_attribute_native_abi.cpp'),
         '/Fe:attribute.exe'])
    # Existing wrappers forward core functions to the same CT Driver. Only16 exports,
    # deliberately no module/launch functions, prove the optional binding is separate.
    foreign=folder/'foreign.c'
    foreign.write_text('__declspec(dllexport) int __stdcall attribute(int *out,int attr,int dev) {(void)attr;(void)dev;*out=123;return 0;}')
    run('foreign',[cl,'/nologo','/utf-8','/W4','/WX','/LD',str(foreign),'/Fe:foreign.dll'])
    for mode in ['minimal','missing','forwarded']:
        exports = CORE + (['cuDeviceGetAttribute'] if mode=='minimal' else [])
        if mode=='forwarded': exports += ['cuDeviceGetAttribute=foreign.attribute']
        deffile=folder/(mode+'.def')
        deffile.write_text('EXPORTS\n'+'\n'.join(exports)+'\n')
        run(mode,[cl,'/nologo','/utf-8','/W4','/WX','/LD',
                  '/DcuDeviceGetAttribute=ct_hidden_attribute' if mode=='forwarded' else '/DCT_ATTRIBUTE_CONTROL',
                  str(ROOT/'tests/p09a_noop_driver.c'),'/Fe:'+mode+'.dll']
                  + ([str(folder/'foreign.lib')] if mode=='forwarded' else [])
                  + ['/link','/DEF:'+str(deffile)])
    files={name:digest(folder/name) for name in ['attribute.exe','ct_cuda.dll','ct_cudart.dll','minimal.dll','missing.dll','forwarded.dll','foreign.dll']}
    runs=[]
    for mode in ['normal','minimal','missing','forwarded','absent']:
        bundle=folder/mode;bundle.mkdir()
        for source,target in [('attribute.exe','attribute.exe'),('ct_cudart.dll','cudart64_12.dll')]:
            shutil.copyfile(folder/source,bundle/target)
        if mode!='absent':
            shutil.copyfile(folder/('ct_cuda.dll' if mode=='normal' else mode+'.dll'),bundle/'nvcuda.dll')
        if mode in ['minimal','missing','forwarded']:
            shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        if mode=='forwarded': shutil.copyfile(folder/'foreign.dll',bundle/'foreign.dll')
        pinned={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        result=subprocess.run([str(bundle/'attribute.exe'),str(bundle/'cudart64_12.dll'),
                               'positive' if mode=='normal' else mode],cwd=bundle,
                              capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr)
        verify_files(bundle,pinned)
        if result.returncode or result.stderr: raise ValueError('native attribute control failed: '+mode)
        value=json.loads(result.stdout)
        if not validate_result(mode, value): raise ValueError('native attribute result failed')
        runs.append(dict(mode=mode,exit_code=result.returncode,result=value,files=pinned,
                         stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    verify_files(folder,files)
    if source_fingerprint(ROOT)!=fingerprint: raise ValueError('source changed')
    manifest=dict(scope='diagnostic_runtime_attribute',release_claim=False,
                  source_fingerprint=fingerprint,producer_sha256=digest(producer),
                  commands=commands,files=files,runs=runs)
    path=folder/'manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    return path

if __name__=='__main__':
    print(json.dumps(dict(status='pass',manifest=build().relative_to(ROOT).as_posix(),release_claim=False)))
