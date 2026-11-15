"""Offline CUDA12.9 bootstrap contract capture; no Driver-version support claim."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from run_cupy_bootstrap import installed,digest
from run_validation import source_fingerprint
from prepare_spirv_tools import extract_pinned
from run_relaxed_nvcc import host_environment
import runtime_bootstrap_contract as contract

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE_SHA='179e9c43b0735ffe67207b3da556eb5a0c50f3047961882b7657d3b822d34ef8'
ARCHIVE_URL='https://developer.download.nvidia.com/compute/cuda/redist/cuda_cudart/windows-x86_64/cuda_cudart-windows-x86_64-12.9.79-archive.zip'
SDK='cuda_cudart-windows-x86_64-12.9.79-archive'
CASES=(('cupy','version',False),('cupy','version',True),('native','version',False),
       ('native','version',True),('native','version_null',True),
       ('native','device_count',False),('native','device_count',True))


def label(case):return '.'.join((case[0],case[1],'observed' if case[2] else 'nominal'))


def evaluate(values):
    if set(values)!={label(c) for c in CASES}:raise ValueError('probe scope')
    for case in CASES[:4]:
        value=values[label(case)]
        if (not contract.version_only(value) or (case[2] and value['patches']<1)
                or (not case[2] and value['patches']!=0)):raise ValueError('version constant/observation changed')
    null=values['native.version_null.observed']
    if (type(null.get('code')) is not int or null['code']!=1 or null.get('value') is not None
            or null.get('trace')!=[] or null.get('restored') is not True
            or type(null.get('patches')) is not int or null['patches']<1):raise ValueError('null version query contract')
    nominal=values['native.device_count.nominal'];observed=values['native.device_count.observed']
    if not contract.native_prefix(nominal,observed):raise ValueError('native bootstrap first blocker changed')
    return dict(status='diagnostic_pass',application_supported=False,runtime_version=12090,
                runtime_patch_identity_proven=False,driver_version_supported=False,
                pure_version_queries=4,null_version_rejected=True,native_prefix=contract.classify(observed['trace']))


def audit(folder,record):
    if record['source_fingerprint']!=source_fingerprint(ROOT):raise ValueError('source changed')
    if digest(Path(record['archive']))!=ARCHIVE_SHA:raise ValueError('Runtime archive identity')
    environment=Path(record['environment']);wheels=Path(record['wheels'])
    if installed(environment,wheels)!=record['installed']:raise ValueError('package payload drift')
    if digest(environment/'Scripts/python.exe')!=record['python_sha256']:raise ValueError('interpreter drift')
    for name,expected in record['artifacts'].items():
        file=(folder/name).resolve()
        if not file.is_relative_to(folder.resolve()) or digest(file)!=expected:raise ValueError('native artifact drift/escape')
    values={}
    if [row['label'] for row in record['runs']]!=[label(c) for c in CASES]:raise ValueError('run order/scope')
    for row,case in zip(record['runs'],CASES):
        bundle=folder/row['label']
        if type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('child failed')
        if row['observations']!={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}:raise ValueError('observation drift')
        value=json.loads((bundle/'stdout.json').read_bytes())
        driver=record['artifacts']['driver-target/debug/ct_cuda.dll']
        runtime=record['artifacts']['sdk/'+SDK+'/bin/cudart64_12.dll'] if case[0]=='native' else None
        if value['provider_sha256']!=driver or digest(bundle/'nvcuda.dll')!=driver:raise ValueError('loaded provider identity')
        if value['runtime_sha256']!=runtime or runtime and digest(bundle/'cudart64_12.dll')!=runtime:raise ValueError('loaded Runtime identity')
        values[row['label']]=value['result']
    return evaluate(values)


def execute_child(folder,record,case,command,bundle,env):
    if source_fingerprint(ROOT)!=record['source_fingerprint']:raise ValueError('source changed before child')
    environment=Path(record['environment'])
    if digest(environment/'Scripts/python.exe')!=record['python_sha256']:raise ValueError('interpreter changed before child')
    # Native-only children import no third-party packages. CuPy children do.
    if case[0]=='cupy' and installed(environment,Path(record['wheels']))!=record['installed']:
        raise ValueError('package changed before child')
    for name,expected in record['artifacts'].items():
        file=(folder/name).resolve()
        if not file.is_relative_to(folder.resolve()) or digest(file)!=expected:
            raise ValueError('SDK/provider/ABI artifact changed before child')
    if digest(bundle/'nvcuda.dll')!=record['artifacts']['driver-target/debug/ct_cuda.dll']:
        raise ValueError('bundle provider changed before child')
    if case[0]=='native' and digest(bundle/'cudart64_12.dll')!=record['artifacts']['sdk/'+SDK+'/bin/cudart64_12.dll']:
        raise ValueError('bundle Runtime changed before child')
    return subprocess.run(command,cwd=bundle,env=env,capture_output=True,timeout=60)


def capture(environment,wheels,archive):
    environment=environment.resolve();wheels=wheels.resolve();archive=archive.resolve()
    identity=installed(environment,wheels)
    folder=ROOT/'.cache/runtime-bootstrap-runs'/uuid.uuid4().hex;folder.mkdir(parents=True)
    extract_pinned(archive,ARCHIVE_SHA,folder/'sdk')
    sdk=folder/'sdk'/SDK
    fingerprint=source_fingerprint(ROOT)
    build=['cargo','build','--locked','-p','ct-cuda','--target-dir',str(folder/'driver-target')]
    with (folder/'build.log').open('wb') as log:
        subprocess.run(build,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180,env=dict(os.environ,CARGO_INCREMENTAL='0'))
    base,env=host_environment(ROOT/'.cache/p09a2-producer/manifest.json',folder)
    abi=[base['host']['tools']['cl.exe']['path'],'/nologo','/utf-8','/W4','/WX','/std:c++17','/c',
         '/I'+str(sdk/'include'),str(ROOT/'tests/bootstrap_resolver_abi.cpp'),'/Fo:'+str(folder/'bootstrap-abi.obj')]
    with (folder/'abi.log').open('wb') as log:
        subprocess.run(abi,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
    if fingerprint!=source_fingerprint(ROOT):raise ValueError('source changed during build/ABI check')
    provider=folder/'driver-target/debug/ct_cuda.dll'
    files=[p for p in (folder/'sdk').rglob('*') if p.is_file()]+[provider,folder/'bootstrap-abi.obj']
    artifacts={p.relative_to(folder).as_posix():digest(p) for p in files}
    python=environment/'Scripts/python.exe'
    record=dict(schema_version=1,source_fingerprint=fingerprint,archive=str(archive),archive_sha256=ARCHIVE_SHA,
                archive_url=ARCHIVE_URL,environment=str(environment),wheels=str(wheels),installed=identity,
                python_sha256=digest(python),artifacts=artifacts,build=build,abi=abi,runs=[])
    for case in CASES:
        if fingerprint!=source_fingerprint(ROOT) or digest(provider)!=artifacts['driver-target/debug/ct_cuda.dll']:
            raise ValueError('source/provider changed before child')
        kind,operation,observe=case;bundle=folder/label(case);bundle.mkdir()
        shutil.copyfile(provider,bundle/'nvcuda.dll')
        if kind=='native':shutil.copyfile(sdk/'bin/cudart64_12.dll',bundle/'cudart64_12.dll')
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('CUDA','CUPY','CT_','NVRTC','PYTHON'))}
        env.update(CUPY_CACHE_DIR=str(bundle/'cupy-cache'),CUDA_PATH=str(bundle))
        command=[str(python),'-I','-S','-B',str(ROOT/'scripts/runtime_bootstrap_worker.py'),
                 '--site',str(environment/'Lib/site-packages'),'--kind',kind,'--operation',operation]+(['--observe'] if observe else [])
        child=execute_child(folder,record,case,command,bundle,env)
        (bundle/'stdout.json').write_bytes(child.stdout);(bundle/'stderr.txt').write_bytes(child.stderr)
        record['runs'].append(dict(label=label(case),exit_code=child.returncode,
            observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}))
        if child.returncode:raise ValueError('native probe failed; inspect private observations')
    record['summary']=audit(folder,record)
    (folder/'capture.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return folder,record['summary']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--environment',type=Path)
    parser.add_argument('--wheels',type=Path)
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--recheck',type=Path)
    args=parser.parse_args()
    if args.recheck:
        folder=args.recheck.resolve()
        if not folder.is_relative_to((ROOT/'.cache/runtime-bootstrap-runs').resolve()):raise ValueError('local capture required')
        record=json.loads((folder/'capture.json').read_bytes());result=audit(folder,record)
        if result!=record['summary']:raise ValueError('summary mismatch')
        (folder/'recheck.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    else:
        if not args.environment or not args.wheels or not args.archive:parser.error('environment, wheels and archive required')
        folder,result=capture(args.environment,args.wheels,args.archive)
    print(json.dumps(dict(run=folder.name,**result)))


if __name__=='__main__':main()
