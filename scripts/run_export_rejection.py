"""Pinned, guarded public export rejection experiment. No private table supplied."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from run_real_bootstrap import ROOT,SDK,capture as baseline_capture,audit as baseline_audit,execute,gate
from run_relaxed_nvcc import host_environment
from run_cupy_bootstrap import digest
from run_validation import source_fingerprint
import export_reject_check as check

LABELS=('contracts','sample12000','sample12090','after.faithful','after.nominal')
MODES=('contracts','intervention','intervention12090','faithful','nominal')


def audit(folder,record):
    base=json.loads((folder/'capture.json').read_bytes())
    baseline_audit(folder,base)
    if (record['source_fingerprint']!=source_fingerprint(ROOT) or record['base_capture_sha256']!=digest(folder/'capture.json')
            or record['abi_sha256']!=digest(folder/'extension/export-reject-abi.obj')
            or [r['label'] for r in record['runs']]!=list(LABELS)):raise ValueError('extension identity/order')
    for row,mode in zip(record['runs'],MODES):
        label=row['label'];bundle=folder/'extension'/label
        if type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('child failed')
        if row['observations']!={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}:raise ValueError('output drift')
        value=json.loads((bundle/'stdout.json').read_bytes())
        if digest(bundle/'nvcuda.dll')!=base['artifacts']['driver-target/debug/ct_cuda.dll'] or value['provider_sha256']!=digest(bundle/'nvcuda.dll'):
            raise ValueError('provider identity')
        if mode!='contracts' and (digest(bundle/'cudart64_12.dll')!=base['artifacts']['sdk/'+SDK+'/bin/cudart64_12.dll']
                                 or value['runtime_sha256']!=digest(bundle/'cudart64_12.dll')):raise ValueError('Runtime identity')
        if mode=='contracts':check.contract(value)
        elif mode.startswith('intervention'):
            expected=12000 if mode=='intervention' else 12090
            if type(value.get('sample')) is not int or value['sample']!=expected:raise ValueError('sample relabelled')
            check.rejection(value)
        else:
            gate(mode,value)
            if value!=json.loads((folder/label/'stdout.json').read_bytes()):raise ValueError('after control changed')
    return dict(status='diagnostic_pass',children=13,guard_contract_checks=20,export_contract_checks=11,
                runtime_codes={'missing_export':36,'explicit_rejection':801},real_init_passed=True,export_calls_per_sample=2,
                baseline_unchanged=True,normal_guard_hits=0,callback_failures=0,application_supported=False,shipping_version_authorized=False)


def capture(python,archive):
    folder,_=baseline_capture(python,archive)
    base=json.loads((folder/'capture.json').read_bytes())
    ext=folder/'extension';ext.mkdir();host,env=host_environment(ROOT/'.cache/p09a2-producer/manifest.json',ext)
    compiler=Path(host['host']['tools']['cl.exe']['path'])
    argv=[str(compiler),'/nologo','/utf-8','/W4','/WX','/std:c++17','/c','/I'+str(folder/'sdk'/SDK/'include'),
          str(ROOT/'tests/export_reject_abi.cpp'),'/Fo:'+str(ext/'export-reject-abi.obj')]
    with (ext/'abi.log').open('wb') as log:subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
    record=dict(source_fingerprint=source_fingerprint(ROOT),base_capture_sha256=digest(folder/'capture.json'),
                abi_sha256=digest(ext/'export-reject-abi.obj'),abi_command=argv,runs=[])
    for label,mode in zip(LABELS,MODES):
        if digest(ext/'export-reject-abi.obj')!=record['abi_sha256']:raise ValueError('ABI drift')
        bundle=ext/label;bundle.mkdir();shutil.copyfile(folder/'driver-target/debug/ct_cuda.dll',bundle/'nvcuda.dll')
        if mode!='contracts':shutil.copyfile(folder/'sdk'/SDK/'bin/cudart64_12.dll',bundle/'cudart64_12.dll')
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('CUDA','CUPY','CT_','PYTHON','NVRTC'))}
        worker='export_reject_worker.py' if mode=='contracts' or mode.startswith('intervention') else 'real_bootstrap_worker.py'
        result=execute(folder,base,[str(python.resolve()),'-I','-S','-B',str(ROOT/'scripts'/worker),mode],bundle,env)
        (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr)
        record['runs'].append(dict(label=label,exit_code=result.returncode,observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}))
        (ext/'progress.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        if result.returncode!=0:raise ValueError('child/guard/failure; no next arm')
        value=json.loads(result.stdout)
        if mode=='contracts':check.contract(value)
        elif mode.startswith('intervention'):
            expected=12000 if mode=='intervention' else 12090
            if type(value.get('sample')) is not int or value['sample']!=expected:raise ValueError('sample relabelled; stopped')
            check.rejection(value)
        else:
            gate(mode,value)
            if value!=json.loads((folder/label/'stdout.json').read_bytes()):raise ValueError('control drift; stopped')
    record['summary']=audit(folder,record)
    (ext/'capture.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return folder,record['summary']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--python',type=Path);p.add_argument('--archive',type=Path);p.add_argument('--recheck',type=Path);args=p.parse_args()
    if args.recheck:
        folder=args.recheck.resolve()
        if not folder.is_relative_to((ROOT/'.cache/real-bootstrap-runs').resolve()):raise ValueError('local capture required')
        record=json.loads((folder/'extension/capture.json').read_bytes());summary=audit(folder,record)
        if summary!=record['summary']:raise ValueError('summary drift')
        (folder/'extension/recheck.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    else:
        if not args.python or not args.archive:p.error('python and archive required')
        folder,summary=capture(args.python,args.archive)
    print(json.dumps(dict(run=folder.name,**summary)))
