"""Pinned synthetic protocol experiment. No numeric CT version or support claim."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import bootstrap_peer_check as check
from run_validation import source_fingerprint
from run_cupy_bootstrap import digest
from run_runtime_bootstrap import ARCHIVE_SHA,SDK
from prepare_spirv_tools import extract_pinned
from run_relaxed_nvcc import host_environment
from runtime_bootstrap_contract import native_prefix
from ct import inspect_pe

ROOT=Path(__file__).resolve().parents[1]
EXPORTS={'cuInit','cuDriverGetVersion','cuGetProcAddress','cuGetProcAddress_v2','cuGetExportTable','ctPeerConfigure','ctPeerSnapshot'}
LABELS=['before.nominal','before.observed','direct']+['peer.'+str(m)+'.'+str(t) for m in range(5) for t in (1,0)]+['after.nominal','after.observed']

def inventory(exports,imports):
    if exports!=EXPORTS:raise ValueError('synthetic callable surface changed')
    if any(any(term in name.lower() for term in ('cuda','ze_loader','opencl','vulkan','nvapi')) for name in imports):
        raise ValueError('GPU/CT dependency in synthetic peer')

def export_names(text):
    if 'forwarded to' in text.lower():raise ValueError('forwarded synthetic export')
    exports=set()
    for line in text.splitlines():
        if not re.match(r'^\s*\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+',line):continue
        match=re.fullmatch(r'\s*\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+(\w+)(?:\s*=\s*(\w+))?\s*',line)
        if not match or match[2] is not None and match[2]!=match[1]:raise ValueError('unverified export annotation/forwarder')
        if match[1] in exports:raise ValueError('duplicate peer export')
        exports.add(match[1])
    return exports

def inspect_inventory(folder):
    parsed=inspect_pe((folder/'peer.dll').read_bytes(),dll=True,diagnostic=True)
    exports=export_names((folder/'peer-exports.txt').read_text(errors='replace'))
    inventory(exports,[i['library'] for i in parsed['imports']])

def execute(folder,record,argv,bundle,env):
    if source_fingerprint(ROOT)!=record['source_fingerprint'] or digest(Path(record['python']))!=record['python_sha256']:
        raise ValueError('source/interpreter changed before child')
    for name,sha in record['artifacts'].items():
        file=(folder/name).resolve()
        if not file.is_relative_to(folder.resolve()) or digest(file)!=sha:raise ValueError('peer/SDK/provider artifact drift')
    role='peer.dll' if bundle.name.startswith('peer.') or bundle.name=='direct' else 'driver-target/debug/ct_cuda.dll'
    if digest(bundle/'nvcuda.dll')!=record['artifacts'][role]:raise ValueError('bundle provider drift')
    if bundle.name!='direct' and digest(bundle/'cudart64_12.dll')!=record['artifacts']['sdk/'+SDK+'/bin/cudart64_12.dll']:
        raise ValueError('bundle Runtime drift')
    return subprocess.run(argv,cwd=bundle,env=env,capture_output=True,timeout=60)

def audit(folder,record):
    if record['source_fingerprint']!=source_fingerprint(ROOT) or digest(Path(record['archive']))!=ARCHIVE_SHA:
        raise ValueError('source/archive drift')
    if digest(Path(record['python']))!=record['python_sha256']:raise ValueError('interpreter drift')
    for name,sha in record['artifacts'].items():
        file=(folder/name).resolve()
        if not file.is_relative_to(folder.resolve()) or digest(file)!=sha:raise ValueError('artifact drift/escape')
    inspect_inventory(folder)
    if [row['label'] for row in record['runs']]!=LABELS:raise ValueError('experiment scope/order')
    values={}
    for row in record['runs']:
        name=row['label'];bundle=folder/name
        if type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('child failed')
        if row['observations']!={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}:raise ValueError('observation drift')
        value=json.loads((bundle/'stdout.json').read_bytes())
        role='peer.dll' if name.startswith('peer.') or name=='direct' else 'driver-target/debug/ct_cuda.dll'
        provider=record['artifacts'][role]
        if value['provider_sha256']!=provider or digest(bundle/'nvcuda.dll')!=provider:raise ValueError('loaded provider identity')
        if name=='direct':
            if value!=dict(scope='synthetic_peer_contract',application_supported=False,checks=19,provider_sha256=provider):raise ValueError('direct peer ABI checks')
        else:
            runtime=record['artifacts']['sdk/'+SDK+'/bin/cudart64_12.dll']
            if value['runtime_sha256']!=runtime or digest(bundle/'cudart64_12.dll')!=runtime:raise ValueError('loaded Runtime identity')
        values[name]=value
    baseline=[]
    for phase in ('before','after'):
        a=values[phase+'.nominal']['result'];b=values[phase+'.observed']['result']
        if not native_prefix(a,b):raise ValueError('real CT baseline changed')
        baseline.append((a,b))
    if baseline[0]!=baseline[1]:raise ValueError('CT before/after disagreement')
    pairs={str(m):check.compare_pair(values['peer.'+str(m)+'.1'],values['peer.'+str(m)+'.0']) for m in range(5)}
    return dict(status='experiment_pass',scope='synthetic_intervention',application_supported=False,ct_compatibility_inferred=False,
                real_ct_baseline_unchanged=True,peer_contract_checks=19,peer_rust_tests=4,pairs=pairs)

def capture(python,archive):
    if sys.platform!='win32':raise ValueError('Windows-only synthetic experiment')
    python=python.resolve();archive=archive.resolve();folder=ROOT/'.cache/bootstrap-peer-runs'/uuid.uuid4().hex;folder.mkdir(parents=True)
    extract_pinned(archive,ARCHIVE_SHA,folder/'sdk');sdk=folder/'sdk'/SDK
    fingerprint=source_fingerprint(ROOT);commands={}
    def run(name,argv,env=None):
        commands[name]=argv
        with (folder/(name+'.log')).open('wb') as log:
            subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    run('peer-build',['rustc','--edition=2021','--crate-type','cdylib','-C','panic=abort','-D','warnings',str(ROOT/'tests/bootstrap_peer.rs'),'-o',str(folder/'peer.dll')])
    run('peer-test-build',['rustc','--edition=2021','--test','-D','warnings',str(ROOT/'tests/bootstrap_peer.rs'),'-o',str(folder/'peer-tests.exe')])
    run('peer-tests',[str(folder/'peer-tests.exe')])
    run('driver',['cargo','build','--locked','-p','ct-cuda','--target-dir',str(folder/'driver-target')],dict(os.environ,CARGO_INCREMENTAL='0'))
    base,env=host_environment(ROOT/'.cache/p09a2-producer/manifest.json',folder)
    compiler=Path(base['host']['tools']['cl.exe']['path'])
    run('abi',[str(compiler),'/nologo','/utf-8','/W4','/WX','/std:c++17','/c','/I'+str(sdk/'include'),str(ROOT/'tests/bootstrap_peer_abi.cpp'),'/Fo:'+str(folder/'peer-abi.obj')],env)
    dumpbin=compiler.parent/'dumpbin.exe'
    with (folder/'peer-exports.txt').open('wb') as out:subprocess.run([str(dumpbin),'/exports',str(folder/'peer.dll')],stdout=out,check=True,timeout=30)
    inspect_inventory(folder)
    if source_fingerprint(ROOT)!=fingerprint:raise ValueError('source changed during build')
    files=[p for p in (folder/'sdk').rglob('*') if p.is_file()]+[folder/'peer.dll',folder/'peer-tests.exe',folder/'peer-abi.obj',folder/'peer-exports.txt',folder/'driver-target/debug/ct_cuda.dll']
    record=dict(schema_version=1,source_fingerprint=fingerprint,archive=str(archive),python=str(python),python_sha256=digest(python),commands=commands,
                artifacts={p.relative_to(folder).as_posix():digest(p) for p in files},runs=[])
    for name in LABELS:
        bundle=folder/name;bundle.mkdir();synthetic=name.startswith('peer.') or name=='direct'
        shutil.copyfile(folder/('peer.dll' if synthetic else 'driver-target/debug/ct_cuda.dll'),bundle/'nvcuda.dll')
        if name!='direct':shutil.copyfile(sdk/'bin/cudart64_12.dll',bundle/'cudart64_12.dll')
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('CUDA','CUPY','CT_','PYTHON','NVRTC'))}
        argv=[str(python),'-I','-S','-B']
        if synthetic:
            mode,trace=('3','1') if name=='direct' else name.split('.')[1:]
            argv += [str(ROOT/'scripts/bootstrap_peer_worker.py'),'--mode',mode,'--trace',trace]+(['--contract'] if name=='direct' else [])
        else:
            argv += [str(ROOT/'scripts/runtime_bootstrap_worker.py'),'--site',str(python.parent.parent/'Lib/site-packages'),'--kind','native','--operation','device_count']+(['--observe'] if name.endswith('observed') else [])
        result=execute(folder,record,argv,bundle,env)
        (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr)
        record['runs'].append(dict(label=name,exit_code=result.returncode,observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}))
        (folder/'progress.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        if result.returncode:raise ValueError('child fault; experiment stopped')
        value=json.loads(result.stdout)
        if name.startswith('peer.'):check.validate_trial(value)
        elif name!='direct' and (value['result']['code']!=35 or value['result']['value']!=-1):raise ValueError('CT baseline changed; experiment stopped')
    record['summary']=audit(folder,record)
    (folder/'capture.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return folder,record['summary']

def main():
    p=argparse.ArgumentParser();p.add_argument('--python',type=Path);p.add_argument('--archive',type=Path);p.add_argument('--recheck',type=Path);args=p.parse_args()
    if args.recheck:
        folder=args.recheck.resolve()
        if not folder.is_relative_to((ROOT/'.cache/bootstrap-peer-runs').resolve()):raise ValueError('local capture required')
        record=json.loads((folder/'capture.json').read_bytes());summary=audit(folder,record)
        if summary!=record['summary']:raise ValueError('experiment summary drift')
        (folder/'recheck.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    else:
        if not args.python or not args.archive:p.error('python and archive required')
        folder,summary=capture(args.python,args.archive)
    print(json.dumps(dict(run=folder.name,status=summary['status'],scope=summary['scope'],application_supported=False,ct_compatibility_inferred=False)))

if __name__=='__main__':main()
