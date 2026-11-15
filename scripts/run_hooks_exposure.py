"""Finite both-table deny experiment, stops at the first private context entry."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from run_table_exposure import capture as previous_capture,audit as previous_audit
from run_typed_tables import audit as fixture_audit
from run_real_bootstrap import ROOT,SDK,execute,gate
from run_relaxed_nvcc import host_environment
from run_cupy_bootstrap import digest
from run_validation import source_fingerprint
from check_bootstrap_tables import COMMIT
import hooks_exposure_check as check

LABELS=('sample12000','sample12090','after.faithful','after.nominal')
MODES=('intervention','intervention12090','faithful','nominal')


def loaded(value,bundle,base,fixture=None):
    for name,key,sha in [('nvcuda.dll','provider_sha256',base['artifacts']['driver-target/debug/ct_cuda.dll']),
                         ('cudart64_12.dll','runtime_sha256',base['artifacts']['sdk/'+SDK+'/bin/cudart64_12.dll'])]:
        if digest(bundle/name)!=sha or value.get(key)!=sha:raise ValueError('loaded provider/Runtime identity')
    if fixture is not None and (digest(bundle/'tables.dll')!=fixture['artifacts']['tables.dll'] or value.get('fixture_sha256')!=digest(bundle/'tables.dll')):
        raise ValueError('loaded fixture identity')


def audit(folder,record):
    parent_path=folder/'table-exposure/capture.json';parent=json.loads(parent_path.read_bytes());previous_audit(folder,parent)
    fixture_path=Path(parent['fixture_manifest']);fixture=json.loads(fixture_path.read_bytes())
    base=json.loads((folder/'capture.json').read_bytes());ext=folder/'hooks-exposure'
    if (record['source_fingerprint']!=source_fingerprint(ROOT) or record['parent_capture_sha256']!=digest(parent_path)
            or record['abi_sha256']!=digest(ext/'hooks-exposure-abi.obj')
            or [r['label'] for r in record['runs']]!=list(LABELS)):raise ValueError('source/order/ABI drift')
    for row,mode in zip(record['runs'],MODES):
        bundle=ext/row['label']
        if type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('child failure')
        if row['observations']!={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}:raise ValueError('observation drift')
        value=json.loads((bundle/'stdout.json').read_bytes());exposure=mode.startswith('intervention')
        loaded(value,bundle,base,fixture if exposure else None)
        if exposure:
            if type(value.get('sample')) is not int or value['sample']!=(12000 if mode=='intervention' else 12090):raise ValueError('sample role')
            check.validate(value)
        else:
            gate(mode,value)
            if value!=json.loads((folder/row['label']/'stdout.json').read_bytes()):raise ValueError('control changed')
    return dict(status='diagnostic_pass',bootstrap_children=21,fixture_rust_tests=3,fixture_native_checks=47,
                runtime_code=3,actual_driver_count=1,device_ordinal=0,private_context_entry_mask=2,hooks_getters_called=False,
                baseline_unchanged=True,application_supported=False,shipping_version_authorized=False)


def capture(python,archive,public_sources):
    folder,_=previous_capture(python,archive,public_sources)
    parent_path=folder/'table-exposure/capture.json';parent=json.loads(parent_path.read_bytes())
    fixture_path=Path(parent['fixture_manifest']);fixture=json.loads(fixture_path.read_bytes())
    base=json.loads((folder/'capture.json').read_bytes());ext=folder/'hooks-exposure';ext.mkdir()
    host,env=host_environment(ROOT/'.cache/p09a2-producer/manifest.json',ext)
    compiler=Path(host['host']['tools']['cl.exe']['path'])
    if digest(compiler)!=fixture['tools']['cl']['sha256']:raise ValueError('ABI compiler differs')
    argv=[str(compiler),'/nologo','/utf-8','/W4','/WX','/std:c++17','/c','/I'+str(folder/'sdk'/SDK/'include'),
          str(ROOT/'tests/hooks_exposure_abi.cpp'),'/Fo:'+str(ext/'hooks-exposure-abi.obj')]
    with (ext/'abi.log').open('wb') as output:subprocess.run(argv,cwd=ext,env=env,stdout=output,stderr=subprocess.STDOUT,check=True,timeout=60)
    record=dict(source_fingerprint=source_fingerprint(ROOT),parent_capture_sha256=digest(parent_path),
                abi_sha256=digest(ext/'hooks-exposure-abi.obj'),abi_command=argv,runs=[])
    for label,mode in zip(LABELS,MODES):
        fixture_audit(fixture_path.parent,fixture)
        if digest(ext/'hooks-exposure-abi.obj')!=record['abi_sha256']:raise ValueError('ABI drift')
        bundle=ext/label;bundle.mkdir();shutil.copyfile(folder/'driver-target/debug/ct_cuda.dll',bundle/'nvcuda.dll')
        shutil.copyfile(folder/'sdk'/SDK/'bin/cudart64_12.dll',bundle/'cudart64_12.dll')
        exposure=mode.startswith('intervention');worker='hooks_exposure_worker.py' if exposure else 'real_bootstrap_worker.py'
        argv=[str(python.resolve()),'-I','-S','-B',str(ROOT/'scripts'/worker),mode]
        if exposure:
            shutil.copyfile(fixture_path.parent/'tables.dll',bundle/'tables.dll')
            if digest(bundle/'tables.dll')!=fixture['artifacts']['tables.dll']:raise ValueError('copied fixture differs')
            argv.extend(['--fixture-manifest',str(fixture_path)])
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('CUDA','CUPY','CT_','PYTHON','NVRTC'))}
        child=execute(folder,base,argv,bundle,env)
        (bundle/'stdout.json').write_bytes(child.stdout);(bundle/'stderr.txt').write_bytes(child.stderr)
        record['runs'].append(dict(label=label,exit_code=child.returncode,observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}))
        (ext/'progress.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        if child.returncode!=0:raise ValueError('native fault/unexpected private hit; stopped')
        value=json.loads(child.stdout);loaded(value,bundle,base,fixture if exposure else None)
        if exposure:
            if type(value.get('sample')) is not int or value['sample']!=(12000 if mode=='intervention' else 12090):raise ValueError('sample relabelled; stopped')
            check.validate(value)
        else:
            gate(mode,value)
            if value!=json.loads((folder/label/'stdout.json').read_bytes()):raise ValueError('control drift; stopped')
    record['summary']=audit(folder,record);(ext/'capture.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return folder,record['summary']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--python',type=Path,default=ROOT/'.cache/r2-apps/cupy-env/Scripts/python.exe')
    p.add_argument('--archive',type=Path,default=ROOT/'.cache/r2b-runtime-12.9/runtime.zip');p.add_argument('--source-root',type=Path,default=ROOT/'.cache/r2g-public'/COMMIT)
    p.add_argument('--recheck',type=Path);args=p.parse_args()
    if args.recheck:
        folder=args.recheck.resolve()
        if not folder.is_relative_to((ROOT/'.cache/real-bootstrap-runs').resolve()):raise ValueError('local capture required')
        record=json.loads((folder/'hooks-exposure/capture.json').read_bytes());summary=audit(folder,record)
        if summary!=record['summary']:raise ValueError('summary drift')
        (folder/'hooks-exposure/recheck.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    else:folder,summary=capture(args.python.resolve(),args.archive.resolve(),args.source_root.resolve())
    print(json.dumps(dict(run=folder.name,**summary)))
