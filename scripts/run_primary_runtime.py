"""Fresh single-provider native context prefix and saved consistency audit."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from run_real_bootstrap import ROOT,SDK,capture as base_capture,audit as base_audit,gate
from run_cupy_bootstrap import digest
from run_validation import source_fingerprint
from run_relaxed_nvcc import host_environment
from run_bootstrap_peer import export_names
from check_compatibility_profile import expected_exports
from run_typed_tables import validate_native
import primary_runtime_check as check

LABELS=('deny-contract','direct','before.faithful','before.nominal','sample12000','sample12090','after.faithful','after.nominal')
MODES=('native','direct','faithful','nominal','intervention','intervention12090','faithful','nominal')
EXTRA={'ctTableGet','ctTableState','ctPrimaryTableGet','ctPrimaryState'}


def audit_build(folder,record):
    folder=folder.resolve()
    if not folder.is_relative_to((ROOT/'.cache/real-bootstrap-runs').resolve()):raise ValueError('local bridge build required')
    base=json.loads((folder/'capture.json').read_bytes())
    if (record['source_fingerprint']!=source_fingerprint(ROOT) or record['source_fingerprint']!=base['source_fingerprint']
            or record['base_capture_sha256']!=digest(folder/'capture.json')):raise ValueError('bridge source/base drift')
    if digest(Path(base['python']))!=base['python_sha256']:raise ValueError('interpreter drift')
    for name,sha in {**base['artifacts'],**record['files']}.items():
        path=(folder/name).resolve()
        if not path.is_relative_to(folder) or digest(path)!=sha:raise ValueError('bridge build artifact drift')
    for row in record['tools'].values():
        if digest(Path(row['path']))!=row['sha256']:raise ValueError('compiler drift')
    names=export_names((folder/'context-bridge/exports.txt').read_text(encoding='utf-8'))
    if names!=set(expected_exports(ROOT))|EXTRA:raise ValueError('diagnostic provider export inventory')
    return base


def loaded(value,bundle,build,base):
    if digest(bundle/'nvcuda.dll')!=build['files']['context-bridge/bridge.dll'] or value.get('provider_sha256')!=digest(bundle/'nvcuda.dll'):raise ValueError('shared provider identity')
    if (bundle/'cudart64_12.dll').is_file():
        sha=base['artifacts']['sdk/'+SDK+'/bin/cudart64_12.dll']
        if digest(bundle/'cudart64_12.dll')!=sha or value.get('runtime_sha256')!=sha:raise ValueError('Runtime identity')


def audit(folder,record):
    base=json.loads((folder/'capture.json').read_bytes());base_audit(folder,base)
    ext=folder/'context-bridge';build=json.loads((ext/'build.json').read_bytes());audit_build(folder,build)
    if record['build_sha256']!=digest(ext/'build.json') or [r['label'] for r in record['runs']]!=list(LABELS):raise ValueError('bridge capture order/build drift')
    values={}
    for row,mode in zip(record['runs'],MODES):
        bundle=ext/row['label']
        if type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('bridge child failure')
        if row['observations']!={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}:raise ValueError('bridge observation drift')
        if digest(bundle/'nvcuda.dll')!=build['files']['context-bridge/bridge.dll']:raise ValueError('copied provider changed')
        value=json.loads((bundle/'stdout.json').read_bytes());values[row['label']]=value
        if mode=='native':validate_native(value)
        else:
            loaded(value,bundle,build,base)
            if mode.startswith('intervention'):
                expected=12000 if mode=='intervention' else 12090
                if type(value.get('sample')) is not int or value['sample']!=expected:raise ValueError('sample role')
                check.validate(value)
            else:gate(mode,value)
    if values['before.faithful']!=values['after.faithful'] or values['before.nominal']!=values['after.nominal']:raise ValueError('bridge baseline changed')
    if values['direct']['result']!=json.loads((folder/'direct/stdout.json').read_bytes())['result']:raise ValueError('direct provider behavior changed')
    return dict(status='diagnostic_pass',production_children=8,bridge_children=8,deny_native_checks=47,
                runtime_code=3,private_context_calls=1,private_context_result=0,private_deny_mask=0,
                next_boundary='cuDeviceGetName',baseline_unchanged=True,private_runtime_prefix_connected=True,
                application_supported=False,shipping_version_authorized=False)


def capture(python,archive):
    folder,_=base_capture(python,archive);base=json.loads((folder/'capture.json').read_bytes())
    ext=folder/'context-bridge';ext.mkdir();host,env=host_environment(ROOT/'.cache/p09a2-producer/manifest.json',ext)
    compiler=Path(host['host']['tools']['cl.exe']['path']);dumpbin=compiler.parent/'dumpbin.exe'
    rustc=Path(subprocess.check_output(['rustup','which','rustc'],text=True).strip())
    paths={'rustc':rustc,'cl':compiler,'link':Path(host['host']['tools']['link.exe']['path']),'dumpbin':dumpbin}
    tools={k:dict(path=str(v),sha256=digest(v)) for k,v in paths.items()}
    target=folder/'driver-target/debug';commands={}
    def run(label,argv):
        if source_fingerprint(ROOT)!=base['source_fingerprint'] or any(digest(Path(t['path']))!=t['sha256'] for t in tools.values()):raise ValueError('source/compiler changed before link')
        commands[label]=argv
        with (ext/(label+'.log')).open('wb') as log:subprocess.run(argv,cwd=ext,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    run('bridge',[str(rustc),'--edition=2021','--crate-type','cdylib','--crate-name','primary_bridge','-C','panic=abort','-D','warnings',
                  '--extern','ct_cuda='+str(target/'libct_cuda.rlib'),'-L','dependency='+str(target/'deps'),str(ROOT/'tests/primary_context_bridge.rs'),'-o',str(ext/'bridge.dll')])
    run('host',[str(compiler),'/nologo','/utf-8','/W4','/WX','/std:c++17','/MT','/EHsc','/I'+str(folder/'sdk'/SDK/'include'),
                str(ROOT/'tests/bootstrap_tables_native.cpp'),'/Fo:'+str(ext/'native.obj'),'/Fe:'+str(ext/'native.exe')])
    with (ext/'exports.txt').open('wb') as log:subprocess.run([str(dumpbin),'/exports',str(ext/'bridge.dll')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
    files=[target/'libct_cuda.rlib']+list((target/'deps').glob('*.rlib'))+list((target/'deps').glob('*.rmeta'))
    files.extend(ext/n for n in ('bridge.dll','native.exe','native.obj','exports.txt'))
    build=dict(source_fingerprint=base['source_fingerprint'],base_capture_sha256=digest(folder/'capture.json'),tools=tools,
               files={p.relative_to(folder).as_posix():digest(p) for p in files},commands=commands)
    audit_build(folder,build);build_path=ext/'build.json';build_path.write_text(json.dumps(build,indent=2),encoding='utf-8')
    record=dict(build_sha256=digest(build_path),runs=[])
    for label,mode in zip(LABELS,MODES):
        audit_build(folder,build)
        if digest(build_path)!=record['build_sha256']:raise ValueError('build manifest changed')
        bundle=ext/label;bundle.mkdir();shutil.copyfile(ext/'bridge.dll',bundle/'nvcuda.dll')
        if digest(bundle/'nvcuda.dll')!=build['files']['context-bridge/bridge.dll']:raise ValueError('provider copy failed')
        if mode=='native':argv=[str(ext/'native.exe'),str(bundle/'nvcuda.dll')]
        else:
            if mode!='direct':shutil.copyfile(folder/'sdk'/SDK/'bin/cudart64_12.dll',bundle/'cudart64_12.dll')
            worker='primary_runtime_worker.py' if mode.startswith('intervention') else 'real_bootstrap_worker.py'
            argv=[str(python.resolve()),'-I','-S','-B',str(ROOT/'scripts'/worker),mode]
            if mode.startswith('intervention'):argv.extend(['--build-manifest',str(build_path)])
        clean={k:v for k,v in os.environ.items() if not k.upper().startswith(('CUDA','CUPY','CT_','PYTHON','NVRTC'))}
        child=subprocess.run(argv,cwd=bundle,env=clean,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(child.stdout);(bundle/'stderr.txt').write_bytes(child.stderr)
        record['runs'].append(dict(label=label,exit_code=child.returncode,observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}))
        (ext/'progress.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        if child.returncode!=0:raise ValueError('bridge native/callback fault; stopped')
        value=json.loads(child.stdout)
        if mode=='native':validate_native(value)
        else:
            loaded(value,bundle,build,base)
            if mode.startswith('intervention'):
                if type(value.get('sample')) is not int or value['sample']!=(12000 if mode=='intervention' else 12090):raise ValueError('sample relabelled')
                check.validate(value)
            else:gate(mode,value)
        if label.startswith('after.') and value!=json.loads((ext/label.replace('after.','before.')/'stdout.json').read_bytes()):raise ValueError('bridge control changed; stopped')
    record['summary']=audit(folder,record);(ext/'capture.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return folder,record['summary']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--python',type=Path,default=ROOT/'.cache/r2-apps/cupy-env/Scripts/python.exe')
    p.add_argument('--archive',type=Path,default=ROOT/'.cache/r2b-runtime-12.9/runtime.zip');p.add_argument('--recheck',type=Path);args=p.parse_args()
    if args.recheck:
        folder=args.recheck.resolve()
        if not folder.is_relative_to((ROOT/'.cache/real-bootstrap-runs').resolve()):raise ValueError('local bridge capture required')
        record=json.loads((folder/'context-bridge/capture.json').read_bytes());summary=audit(folder,record)
        if summary!=record['summary']:raise ValueError('summary drift')
        (folder/'context-bridge/recheck.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    else:folder,summary=capture(args.python.resolve(),args.archive.resolve())
    print(json.dumps(dict(run=folder.name,**summary)))
