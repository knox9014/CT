"""Guarded real-provider bootstrap counterfactual; no shipping version change."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import uuid
from run_runtime_bootstrap import ARCHIVE_SHA,SDK
from run_cupy_bootstrap import digest
from run_validation import source_fingerprint
from prepare_spirv_tools import extract_pinned
from run_relaxed_nvcc import host_environment
from run_bootstrap_peer import export_names
from check_compatibility_profile import expected_exports
import real_bootstrap_check as check

ROOT=Path(__file__).resolve().parents[1]
ARMS={'before.nominal':'nominal','before.faithful':'faithful','contracts':'contracts','direct':'direct',
      'sample12000':'intervention','sample12090':'intervention12090','after.faithful':'faithful','after.nominal':'nominal'}

def kernel_surface(names):
    routes={n for n in names if 'Launch' in n or n.startswith(('cuModuleLoad','cuLibraryLoad','cuLink'))}
    if routes!={'cuModuleLoadData','cuLaunchKernel'}:raise ValueError('unreviewed code-loading/submission route')

def execute(folder,record,argv,bundle,env):
    if source_fingerprint(ROOT)!=record['source_fingerprint'] or digest(Path(record['python']))!=record['python_sha256']:
        raise ValueError('source/interpreter changed before child')
    for name,sha in record['artifacts'].items():
        file=(folder/name).resolve()
        if not file.is_relative_to(folder.resolve()) or digest(file)!=sha:raise ValueError('provider/SDK/ABI drift before child')
    if digest(bundle/'nvcuda.dll')!=record['artifacts']['driver-target/debug/ct_cuda.dll']:raise ValueError('bundle provider drift')
    if ARMS[bundle.name] not in ('direct','contracts') and digest(bundle/'cudart64_12.dll')!=record['artifacts']['sdk/'+SDK+'/bin/cudart64_12.dll']:
        raise ValueError('bundle Runtime drift')
    return subprocess.run(argv,cwd=bundle,env=env,capture_output=True,timeout=60)

def gate(mode,value,direct_count=None):
    if mode in ('nominal','faithful'):check.baseline(value,faithful=mode=='faithful')
    elif mode=='contracts':check.guard_contract(value)
    elif mode=='direct':return check.ordinary(value)
    else:
        sample=12000 if mode=='intervention' else 12090
        if type(value.get('sample')) is not int or value['sample']!=sample:raise ValueError('counterfactual relabelled')
        return check.counterfactual(value,direct_count)

def audit(folder,record):
    if source_fingerprint(ROOT)!=record['source_fingerprint'] or digest(Path(record['archive']))!=ARCHIVE_SHA:raise ValueError('source/archive drift')
    if digest(Path(record['python']))!=record['python_sha256']:raise ValueError('interpreter drift')
    for name,sha in record['artifacts'].items():
        file=(folder/name).resolve()
        if not file.is_relative_to(folder.resolve()) or digest(file)!=sha:raise ValueError('artifact drift/escape')
    names=export_names((folder/'driver-exports.txt').read_text(errors='replace'))
    if names!=set(expected_exports(ROOT)):raise ValueError('provider export inventory')
    kernel_surface(names)
    if [r['label'] for r in record['runs']]!=list(ARMS):raise ValueError('arm order/scope')
    values={};direct_count=None;counterfactuals={}
    for row in record['runs']:
        name=row['label'];mode=ARMS[name];bundle=folder/name
        if type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('child/guard/native failure')
        if row['observations']!={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}:raise ValueError('observations changed')
        value=json.loads((bundle/'stdout.json').read_bytes())
        driver=record['artifacts']['driver-target/debug/ct_cuda.dll']
        runtime=record['artifacts']['sdk/'+SDK+'/bin/cudart64_12.dll'] if mode not in ('direct','contracts') else None
        if value['provider_sha256']!=driver or digest(bundle/'nvcuda.dll')!=driver:raise ValueError('loaded provider identity')
        if value['runtime_sha256']!=runtime or runtime and digest(bundle/'cudart64_12.dll')!=runtime:raise ValueError('loaded Runtime identity')
        result=gate(mode,value,direct_count)
        if mode=='direct':direct_count=result
        if mode.startswith('intervention'):counterfactuals[str(value['sample'])]=result
        values[name]=value
    if values['before.nominal']!=values['after.nominal'] or values['before.faithful']!=values['after.faithful']:
        raise ValueError('before/after controls changed')
    return dict(status='diagnostic_pass',scope='ct_guarded_counterfactual',application_supported=False,
                shipping_version_authorized=False,real_driver_count=direct_count,device_name=values['direct']['result']['device_name'],
                baseline_unchanged=True,guard_contract_checks=20,normal_guard_hits=0,callback_failures=0,
                counterfactuals=counterfactuals,required_missing_api_identified=False)

def capture(python,archive):
    if sys.platform!='win32':raise ValueError('Windows-only diagnostic')
    python=python.resolve();archive=archive.resolve()
    abi=subprocess.check_output([str(python),'-I','-S','-c','import sys,struct;print(str(sys.version_info[:2])+":"+str(struct.calcsize("P")))'],text=True).strip()
    if abi!='(3, 14):8':raise ValueError('pinned host ABI required')
    folder=ROOT/'.cache/real-bootstrap-runs'/uuid.uuid4().hex;folder.mkdir(parents=True)
    fingerprint=source_fingerprint(ROOT);extract_pinned(archive,ARCHIVE_SHA,folder/'sdk');sdk=folder/'sdk'/SDK
    commands={}
    def run(label,argv,env=None):
        commands[label]=argv
        with (folder/(label+'.log')).open('wb') as log:subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    run('driver',['cargo','build','--locked','-p','ct-cuda','--target-dir',str(folder/'driver-target')],dict(os.environ,CARGO_INCREMENTAL='0'))
    base,env=host_environment(ROOT/'.cache/p09a2-producer/manifest.json',folder)
    compiler=Path(base['host']['tools']['cl.exe']['path'])
    run('abi',[str(compiler),'/nologo','/utf-8','/W4','/WX','/std:c++17','/c','/I'+str(sdk/'include'),str(ROOT/'tests/real_bootstrap_abi.cpp'),'/Fo:'+str(folder/'real-bootstrap-abi.obj')],env)
    with (folder/'driver-exports.txt').open('wb') as log:subprocess.run([str(compiler.parent/'dumpbin.exe'),'/exports',str(folder/'driver-target/debug/ct_cuda.dll')],stdout=log,check=True,timeout=30)
    names=export_names((folder/'driver-exports.txt').read_text(errors='replace'))
    if names!=set(expected_exports(ROOT)):raise ValueError('actual Driver export inventory')
    kernel_surface(names)
    if source_fingerprint(ROOT)!=fingerprint:raise ValueError('source changed during build/ABI check')
    files=[p for p in (folder/'sdk').rglob('*') if p.is_file()]+[folder/'driver-target/debug/ct_cuda.dll',folder/'real-bootstrap-abi.obj',folder/'driver-exports.txt']
    record=dict(schema_version=1,source_fingerprint=fingerprint,archive=str(archive),python=str(python),python_sha256=digest(python),
                artifacts={p.relative_to(folder).as_posix():digest(p) for p in files},commands=commands,runs=[])
    direct_count=None
    for label,mode in ARMS.items():
        bundle=folder/label;bundle.mkdir();shutil.copyfile(folder/'driver-target/debug/ct_cuda.dll',bundle/'nvcuda.dll')
        if mode not in ('direct','contracts'):shutil.copyfile(sdk/'bin/cudart64_12.dll',bundle/'cudart64_12.dll')
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('CUDA','CUPY','CT_','PYTHON','NVRTC'))}
        argv=[str(python),'-I','-S','-B',str(ROOT/'scripts/real_bootstrap_worker.py'),mode]
        result=execute(folder,record,argv,bundle,env)
        (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr)
        record['runs'].append(dict(label=label,exit_code=result.returncode,observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}))
        (folder/'progress.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        if result.returncode!=0:raise ValueError('child/guard/native failure; no next arm permitted')
        value=json.loads(result.stdout);checked=gate(mode,value,direct_count)
        if mode=='direct':direct_count=checked
    record['summary']=audit(folder,record)
    (folder/'capture.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return folder,record['summary']

def main():
    p=argparse.ArgumentParser();p.add_argument('--python',type=Path);p.add_argument('--archive',type=Path);p.add_argument('--recheck',type=Path);args=p.parse_args()
    if args.recheck:
        folder=args.recheck.resolve()
        if not folder.is_relative_to((ROOT/'.cache/real-bootstrap-runs').resolve()):raise ValueError('local capture required')
        record=json.loads((folder/'capture.json').read_bytes());summary=audit(folder,record)
        if summary!=record['summary']:raise ValueError('summary drift')
        (folder/'recheck.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    else:
        if not args.python or not args.archive:p.error('python and archive required')
        folder,summary=capture(args.python,args.archive)
    print(json.dumps(dict(run=folder.name,**summary)))

if __name__=='__main__':main()
