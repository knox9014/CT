"""Minimal labelled table-pointer presentation after independent fixture proof."""
import argparse
import json
import os
from pathlib import Path
import shutil
from run_typed_tables import capture as fixture_capture,audit as fixture_audit
from run_export_rejection import capture as reject_capture,audit as reject_audit
from run_real_bootstrap import ROOT,SDK,execute,gate
from run_validation import source_fingerprint
from run_cupy_bootstrap import digest
from check_bootstrap_tables import COMMIT
import table_exposure_check as check

LABELS=('sample12000','sample12090','after.faithful','after.nominal')
MODES=('intervention','intervention12090','faithful','nominal')


def audit(folder,record):
    fixture=Path(record['fixture_manifest']).resolve()
    if fixture.name!='capture.json' or not fixture.parent.is_relative_to((ROOT/'.cache/typed-table-runs').resolve()):raise ValueError('fixture scope')
    fixture_record=json.loads(fixture.read_bytes());fixture_audit(fixture.parent,fixture_record)
    reject_record=json.loads((folder/'extension/capture.json').read_bytes());reject_audit(folder,reject_record)
    base=json.loads((folder/'capture.json').read_bytes())
    if (record['source_fingerprint']!=source_fingerprint(ROOT) or record['fixture_capture_sha256']!=digest(fixture)
            or record['rejection_capture_sha256']!=digest(folder/'extension/capture.json')
            or [r['label'] for r in record['runs']]!=list(LABELS)):raise ValueError('scope/source/order drift')
    for row,mode in zip(record['runs'],MODES):
        bundle=folder/'table-exposure'/row['label']
        if type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('child failure')
        if row['observations']!={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}:raise ValueError('output drift')
        value=json.loads((bundle/'stdout.json').read_bytes())
        for name,expected in [('nvcuda.dll',base['artifacts']['driver-target/debug/ct_cuda.dll']),
                              ('cudart64_12.dll',base['artifacts']['sdk/'+SDK+'/bin/cudart64_12.dll'])]:
            if digest(bundle/name)!=expected:raise ValueError('copied provider/Runtime changed')
        if value['provider_sha256']!=digest(bundle/'nvcuda.dll') or value['runtime_sha256']!=digest(bundle/'cudart64_12.dll'):raise ValueError('loaded identity')
        if mode.startswith('intervention'):
            expected=12000 if mode=='intervention' else 12090
            if type(value.get('sample')) is not int or value['sample']!=expected:raise ValueError('sample role')
            if digest(bundle/'tables.dll')!=fixture_record['artifacts']['tables.dll'] or value['fixture_sha256']!=digest(bundle/'tables.dll'):raise ValueError('fixture identity')
            check.validate(value)
        else:
            gate(mode,value)
            if value!=json.loads((folder/row['label']/'stdout.json').read_bytes()):raise ValueError('control drift')
    return dict(status='diagnostic_pass',bootstrap_children=17,fixture_rust_tests=3,fixture_native_checks=47,
                export_queries_per_sample=3,private_callback_mask=0,next_query=check.NEXT,real_init_passed=True,
                runtime_code=801,baseline_unchanged=True,application_supported=False,shipping_version_authorized=False)


def capture(python,archive,public_sources):
    fixture,_=fixture_capture(archive,public_sources)
    fixture_manifest=fixture/'capture.json';fixture_record=json.loads(fixture_manifest.read_bytes())
    folder,_=reject_capture(python,archive)
    base=json.loads((folder/'capture.json').read_bytes())
    ext=folder/'table-exposure';ext.mkdir()
    record=dict(source_fingerprint=source_fingerprint(ROOT),fixture_manifest=str(fixture_manifest),fixture_capture_sha256=digest(fixture_manifest),
                rejection_capture_sha256=digest(folder/'extension/capture.json'),runs=[])
    for label,mode in zip(LABELS,MODES):
        fixture_audit(fixture,fixture_record)
        bundle=ext/label;bundle.mkdir()
        shutil.copyfile(folder/'driver-target/debug/ct_cuda.dll',bundle/'nvcuda.dll')
        shutil.copyfile(folder/'sdk'/SDK/'bin/cudart64_12.dll',bundle/'cudart64_12.dll')
        exposure=mode.startswith('intervention')
        worker='table_exposure_worker.py' if exposure else 'real_bootstrap_worker.py'
        argv=[str(python.resolve()),'-I','-S','-B',str(ROOT/'scripts'/worker),mode]
        if exposure:
            shutil.copyfile(fixture/'tables.dll',bundle/'tables.dll')
            if digest(bundle/'tables.dll')!=fixture_record['artifacts']['tables.dll']:raise ValueError('copy drift')
            argv.extend(['--fixture-manifest',str(fixture_manifest)])
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('CUDA','CUPY','CT_','PYTHON','NVRTC'))}
        child=execute(folder,base,argv,bundle,env)
        (bundle/'stdout.json').write_bytes(child.stdout);(bundle/'stderr.txt').write_bytes(child.stderr)
        record['runs'].append(dict(label=label,exit_code=child.returncode,observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}))
        (ext/'progress.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        if child.returncode!=0:raise ValueError('private hit/fault/guard/failure; no next child')
        value=json.loads(child.stdout)
        for name,key,expected_sha in [('nvcuda.dll','provider_sha256',base['artifacts']['driver-target/debug/ct_cuda.dll']),
                                      ('cudart64_12.dll','runtime_sha256',base['artifacts']['sdk/'+SDK+'/bin/cudart64_12.dll'])]:
            if digest(bundle/name)!=expected_sha or value.get(key)!=expected_sha:raise ValueError('loaded identity differs; stopped')
        if exposure:
            expected=12000 if mode=='intervention' else 12090
            if type(value.get('sample')) is not int or value['sample']!=expected:raise ValueError('sample relabelled; stopped')
            if value.get('fixture_sha256')!=fixture_record['artifacts']['tables.dll'] or digest(bundle/'tables.dll')!=value['fixture_sha256']:
                raise ValueError('fixture identity differs; stopped')
            check.validate(value)
        else:
            gate(mode,value)
            if value!=json.loads((folder/label/'stdout.json').read_bytes()):raise ValueError('control changed; stopped')
    record['summary']=audit(folder,record)
    (ext/'capture.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return folder,record['summary']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--python',type=Path,default=ROOT/'.cache/r2-apps/cupy-env/Scripts/python.exe')
    p.add_argument('--archive',type=Path,default=ROOT/'.cache/r2b-runtime-12.9/runtime.zip');p.add_argument('--source-root',type=Path,default=ROOT/'.cache/r2g-public'/COMMIT)
    p.add_argument('--recheck',type=Path);args=p.parse_args()
    if args.recheck:
        folder=args.recheck.resolve()
        if not folder.is_relative_to((ROOT/'.cache/real-bootstrap-runs').resolve()):raise ValueError('local capture required')
        record=json.loads((folder/'table-exposure/capture.json').read_bytes());summary=audit(folder,record)
        if summary!=record['summary']:raise ValueError('summary drift')
        (folder/'table-exposure/recheck.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    else:folder,summary=capture(args.python.resolve(),args.archive.resolve(),args.source_root.resolve())
    print(json.dumps(dict(run=folder.name,**summary)))
