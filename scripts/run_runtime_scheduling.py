"""Guarded scheduling prefix and one real unsupported attribute; saved audit."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from cache_budget import ensure_budget,GIB
from run_runtime_metadata import capture as parent_capture,audit as parent_audit
from run_primary_runtime import loaded
from run_real_bootstrap import ROOT,SDK
from run_cupy_bootstrap import digest
from run_validation import source_fingerprint
import runtime_scheduling_check as check

LABELS=('sample12000','sample12090','after.strict1','after.strict2')
MODES=('intervention','intervention12090','strict-control','strict-control')


def validate_child(folder,bundle,build,base,mode,value):
    runtime=bundle/'cudart64_12.dll'
    if mode=='strict-control':
        if runtime.exists() or runtime.is_symlink() or value.get('runtime_sha256') is not None:raise ValueError('strict control loaded a Runtime')
    else:
        expected=base['artifacts']['sdk/'+SDK+'/bin/cudart64_12.dll']
        if (not runtime.is_file() or runtime.is_symlink() or runtime.is_junction()
                or digest(runtime)!=expected or value.get('runtime_sha256')!=expected):raise ValueError('required virtual Runtime identity')
    loaded(value,bundle,build,base)
    if mode=='strict-control':check.validate_strict_control(value);return None
    if type(value.get('sample')) is not int or value['sample']!=(12000 if mode=='intervention' else 12090):raise ValueError('virtual sample role')
    result=check.validate(value)
    direct=json.loads((folder/'direct/stdout.json').read_bytes())
    if result['actual_name']!=direct['result']['device_name']:raise ValueError('direct device differs')
    return result


def audit(folder,record):
    parent_path=folder/'metadata-prefix/capture.json';parent=json.loads(parent_path.read_bytes());parent_audit(folder,parent)
    build=json.loads((folder/'context-bridge/build.json').read_bytes());base=json.loads((folder/'capture.json').read_bytes());ext=folder/'scheduling-metadata'
    if record['parent_capture_sha256']!=digest(parent_path) or [r['label'] for r in record['runs']]!=list(LABELS):raise ValueError('virtual parent/order drift')
    results=[];controls=[]
    for row,mode in zip(record['runs'],MODES):
        bundle=ext/row['label']
        if type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('virtual child failed')
        if row['observations']!={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}:raise ValueError('virtual observation drift')
        value=json.loads((bundle/'stdout.json').read_bytes());result=validate_child(folder,bundle,build,base,mode,value)
        if result is not None:results.append(result)
        else:controls.append(value)
    if results[0]!=results[1] or controls[0]!=controls[1]:raise ValueError('virtual samples/strict controls differ')
    return dict(status='diagnostic_pass',native_children=24,deny_native_checks=47,runtime_code=3,
                actual_name=results[0]['actual_name'],actual_total_bytes=results[0]['actual_total_bytes'],
                actual_attribute=results[0]['actual_attribute'],actual_attribute_code=801,actual_overlap=0,actual_async_engines=0,virtual_major_minor=[5,2],software_target_only=True,
                default_strict_attribute=75,default_strict_code=801,baseline_unchanged=True,
                application_supported=False,shipping_version_authorized=False)


def capture(python,archive):
    if source_fingerprint(ROOT)!='2f0896b95606c94e0bb98d45524745ab161befcf584f147fb2bb99a9e7af6866':
        raise ValueError('historical R2t capture requires its frozen source; use the immutable R2t source for replay')
    ensure_budget(ROOT,2*GIB)
    folder,_=parent_capture(python,archive);parent_path=folder/'metadata-prefix/capture.json'
    build=json.loads((folder/'context-bridge/build.json').read_bytes());base=json.loads((folder/'capture.json').read_bytes())
    parent=json.loads(parent_path.read_bytes());ext=folder/'scheduling-metadata';ext.mkdir()
    record=dict(parent_capture_sha256=digest(parent_path),runs=[]);first=None
    for label,mode in zip(LABELS,MODES):
        parent_audit(folder,parent)
        if digest(parent_path)!=record['parent_capture_sha256']:raise ValueError('virtual parent changed')
        bundle=ext/label;bundle.mkdir();shutil.copyfile(folder/'context-bridge/bridge.dll',bundle/'nvcuda.dll')
        if mode!='strict-control':shutil.copyfile(folder/'sdk'/SDK/'bin/cudart64_12.dll',bundle/'cudart64_12.dll')
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('CUDA','CUPY','CT_','PYTHON','NVRTC'))}
        if mode!='strict-control':env['CT_VIRTUAL_TARGET']=check.POLICY
        argv=[str(python.resolve()),'-I','-S','-B',str(ROOT/'scripts/runtime_scheduling_worker.py'),mode,'--build-manifest',str(folder/'context-bridge/build.json')]
        child=subprocess.run(argv,cwd=bundle,env=env,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(child.stdout);(bundle/'stderr.txt').write_bytes(child.stderr)
        record['runs'].append(dict(label=label,exit_code=child.returncode,observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}))
        (ext/'progress.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        if child.returncode!=0:raise ValueError('virtual native/callback failure; stopped')
        value=json.loads(child.stdout);result=validate_child(folder,bundle,build,base,mode,value)
        if result is not None:
            if first is None:first=result
            elif result!=first:raise ValueError('virtual samples differ; stopped')
    record['summary']=audit(folder,record);(ext/'capture.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return folder,record['summary']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--python',type=Path,default=ROOT/'.cache/r2-apps/cupy-env/Scripts/python.exe')
    p.add_argument('--archive',type=Path,default=ROOT/'.cache/r2b-runtime-12.9/runtime.zip');p.add_argument('--recheck',type=Path);args=p.parse_args()
    if args.recheck:
        folder=args.recheck.resolve()
        if not folder.is_relative_to((ROOT/'.cache/real-bootstrap-runs').resolve()):raise ValueError('local virtual capture required')
        record=json.loads((folder/'scheduling-metadata/capture.json').read_bytes());summary=audit(folder,record)
        if summary!=record['summary']:raise ValueError('virtual summary drift')
        (folder/'scheduling-metadata/recheck.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    else:folder,summary=capture(args.python.resolve(),args.archive.resolve())
    print(json.dumps(dict(run=folder.name,**summary)))
