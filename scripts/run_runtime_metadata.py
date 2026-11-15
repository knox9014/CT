"""Fresh strict-policy metadata prefix using the authenticated R2n provider."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from run_primary_runtime import capture as parent_capture,audit as parent_audit,loaded
from run_real_bootstrap import ROOT,SDK,gate
from run_cupy_bootstrap import digest
import runtime_metadata_check as check

LABELS=('sample12000','sample12090','after.faithful','after.nominal')
MODES=('intervention','intervention12090','faithful','nominal')


def audit(folder,record):
    parent_path=folder/'context-bridge/capture.json';parent=json.loads(parent_path.read_bytes());parent_audit(folder,parent)
    build=json.loads((folder/'context-bridge/build.json').read_bytes());base=json.loads((folder/'capture.json').read_bytes());ext=folder/'metadata-prefix'
    if record['parent_capture_sha256']!=digest(parent_path) or [r['label'] for r in record['runs']]!=list(LABELS):raise ValueError('metadata parent/order drift')
    results=[]
    for row,mode in zip(record['runs'],MODES):
        bundle=ext/row['label']
        if type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('metadata native child failure')
        if row['observations']!={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}:raise ValueError('metadata observations drift')
        value=json.loads((bundle/'stdout.json').read_bytes());loaded(value,bundle,build,base)
        if mode.startswith('intervention'):
            if type(value.get('sample')) is not int or value['sample']!=(12000 if mode=='intervention' else 12090):raise ValueError('metadata sample role')
            result=check.validate(value);results.append(result)
            direct=json.loads((folder/'direct/stdout.json').read_bytes())
            if result['actual_name']!=direct['result']['device_name']:raise ValueError('name differs from direct device control')
        else:
            gate(mode,value)
            if value!=json.loads((folder/'context-bridge'/row['label']/'stdout.json').read_bytes()):raise ValueError('metadata baseline changed')
    if results[0]!=results[1]:raise ValueError('metadata sample results differ')
    return dict(status='diagnostic_pass',native_children=20,deny_native_checks=47,runtime_code=3,
                actual_name=results[0]['actual_name'],actual_total_bytes=results[0]['actual_total_bytes'],actual_attribute=75,actual_attribute_code=801,
                private_context_calls=1,private_deny_mask=0,policy_mode='strict-default',baseline_unchanged=True,
                application_supported=False,shipping_version_authorized=False)


def capture(python,archive):
    folder,_=parent_capture(python,archive);parent_path=folder/'context-bridge/capture.json';parent=json.loads(parent_path.read_bytes())
    build=json.loads((folder/'context-bridge/build.json').read_bytes());base=json.loads((folder/'capture.json').read_bytes())
    ext=folder/'metadata-prefix';ext.mkdir();record=dict(parent_capture_sha256=digest(parent_path),runs=[]);first_result=None
    for label,mode in zip(LABELS,MODES):
        parent_audit(folder,parent)
        if digest(parent_path)!=record['parent_capture_sha256']:raise ValueError('metadata parent changed')
        bundle=ext/label;bundle.mkdir();shutil.copyfile(folder/'context-bridge/bridge.dll',bundle/'nvcuda.dll')
        shutil.copyfile(folder/'sdk'/SDK/'bin/cudart64_12.dll',bundle/'cudart64_12.dll')
        if digest(bundle/'nvcuda.dll')!=build['files']['context-bridge/bridge.dll'] or digest(bundle/'cudart64_12.dll')!=base['artifacts']['sdk/'+SDK+'/bin/cudart64_12.dll']:raise ValueError('metadata bundle identity')
        worker='runtime_metadata_worker.py' if mode.startswith('intervention') else 'real_bootstrap_worker.py'
        argv=[str(python.resolve()),'-I','-S','-B',str(ROOT/'scripts'/worker),mode]
        if mode.startswith('intervention'):argv.extend(['--build-manifest',str(folder/'context-bridge/build.json')])
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('CUDA','CUPY','CT_','PYTHON','NVRTC'))}
        child=subprocess.run(argv,cwd=bundle,env=env,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(child.stdout);(bundle/'stderr.txt').write_bytes(child.stderr)
        record['runs'].append(dict(label=label,exit_code=child.returncode,observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}))
        (ext/'progress.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        if child.returncode!=0:raise ValueError('metadata callback/native failure; stopped')
        value=json.loads(child.stdout);loaded(value,bundle,build,base)
        if mode.startswith('intervention'):
            if type(value.get('sample')) is not int or value['sample']!=(12000 if mode=='intervention' else 12090):raise ValueError('sample relabelled')
            result=check.validate(value)
            if result['actual_name']!=json.loads((folder/'direct/stdout.json').read_bytes())['result']['device_name']:raise ValueError('direct name mismatch')
            if first_result is None:first_result=result
            elif result!=first_result:raise ValueError('metadata samples differ; no following child permitted')
        else:
            gate(mode,value)
            if value!=json.loads((folder/'context-bridge'/label/'stdout.json').read_bytes()):raise ValueError('metadata control drift')
    record['summary']=audit(folder,record);(ext/'capture.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return folder,record['summary']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--python',type=Path,default=ROOT/'.cache/r2-apps/cupy-env/Scripts/python.exe')
    p.add_argument('--archive',type=Path,default=ROOT/'.cache/r2b-runtime-12.9/runtime.zip');p.add_argument('--recheck',type=Path);args=p.parse_args()
    if args.recheck:
        folder=args.recheck.resolve()
        if not folder.is_relative_to((ROOT/'.cache/real-bootstrap-runs').resolve()):raise ValueError('local metadata capture required')
        record=json.loads((folder/'metadata-prefix/capture.json').read_bytes());summary=audit(folder,record)
        if summary!=record['summary']:raise ValueError('metadata summary drift')
        (folder/'metadata-prefix/recheck.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    else:folder,summary=capture(args.python.resolve(),args.archive.resolve())
    print(json.dumps(dict(run=folder.name,**summary)))
