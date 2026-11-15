"""R1c bounded single-thread Runtime reuse and isolated Driver module retirement."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import lifecycle_check as contract
from run_matrix_rounding import build as build_parent,audit as audit_parent
from run_relaxed_nvcc import command,compiler_args,host_environment,digest,verify_files,ptx_tokens,payload
from run_validation import source_fingerprint
from check_compatibility_profile import expected_exports
ROOT=Path(__file__).resolve().parents[1]
SCOPE='diagnostic_bounded_resource_lifetime_v1'
PROFILE=dict(runtime_cycles=256,driver_cycles=160,control_cycles=8,seeds=[193,731],native_live_limit=128,worker_threads=1,timeout_seconds=180,driver_runtime_interop=False)
SCENARIOS=(('runtime','positive',193,256),('runtime','positive',731,256),('runtime','noop_launch',193,8),('runtime','noop_copy',731,8),
           ('driver','positive',193,160),('driver','positive',731,160),('driver','noop_launch',193,8),('driver','noop_copy',731,8),('driver','noop_unload',193,8))
FILES={'ct_cuda.dll','lifetime-runtime.dll','lifecycle.exe','lifecycle.cu','vector-lifetime.ptx','lifecycle-driver.def','keep-lifecycle/lifecycle.ptx','keep-lifecycle/lifecycle.fatbin'}|{'lifetime-'+m+'.dll' for m in ('noop_launch','noop_copy','noop_unload')}

def recipes(folder,producer,base):
    cuda=[('lifecycle.cu' if x=='vector.cu' else 'lifecycle.exe' if x=='default.exe' else 'keep-lifecycle' if x=='keep' else x) for x in compiler_args(folder,producer.parent,base['host'])]
    cl=base['host']['tools']['cl.exe']['path'];commands={'cuda':cuda}
    for mode,macro in [('noop_launch','LIFETIME_NOOP_LAUNCH'),('noop_copy','NOOP_COPY'),('noop_unload','LIFETIME_NOOP_UNLOAD')]:
        commands[mode]=[cl,'/nologo','/utf-8','/W4','/WX','/LD','/D'+macro,str(ROOT/'tests/lifecycle_driver_proxy.c'),'/Fe:lifetime-'+mode+'.dll','/link','/DEF:'+str(folder/'lifecycle-driver.def')]
    return commands

def payloads(files,kind,mode):
    p={'nvcuda.dll':files['ct_cuda.dll' if mode=='positive' else 'lifetime-'+mode+'.dll']}
    if kind=='runtime':p.update({'lifecycle.exe':files['lifecycle.exe'],'cudart64_12.dll':files['lifetime-runtime.dll']})
    else:p['vector.ptx']=files['vector-lifetime.ptx']
    if mode!='positive':p['ct_underlying.dll']=files['ct_cuda.dll']
    return p

def argv(bundle,kind,seed,cycles):
    return ([str(bundle/'lifecycle.exe')] if kind=='runtime' else [sys.executable,str(ROOT/'scripts/lifecycle_driver_worker.py')])+[str(seed),str(cycles)]

def verify_run(folder,files,row):
    keys={'kind','mode','seed','cycles','bundle','command','files','observations','exit_code','numerical'}
    if type(row) is not dict or set(row)!=keys or (row['kind'],row['mode'],row['seed'],row['cycles']) not in SCENARIOS:raise ValueError('lifetime observation scope')
    kind,mode,seed,cycles=(row[k] for k in ('kind','mode','seed','cycles'))
    name=row['bundle']
    if type(name) is not str or Path(name).is_absolute():raise ValueError('lifetime bundle name')
    bundle=(folder/name).resolve()
    if not bundle.is_relative_to((folder/'resource-lifetime-runs').resolve()):raise ValueError('lifetime bundle escape')
    wanted=payloads(files,kind,mode)
    if not contract.exact(row['files'],wanted) or row['command']!=argv(bundle,kind,seed,cycles):raise ValueError('lifetime command/provider identity')
    verify_files(bundle,wanted)
    if type(row['observations']) is not dict or set(row['observations'])!={'stdout.json','stderr.txt'} or {p.name for p in bundle.iterdir()}!=set(wanted)|set(row['observations']):raise ValueError('lifetime observation files')
    verify_files(bundle,row['observations'])
    if type(row['exit_code']) is not int or (bundle/'stderr.txt').read_bytes():raise ValueError('lifetime API/worker failure')
    value=json.loads((bundle/'stdout.json').read_bytes())
    if mode=='noop_unload':
        if row['exit_code']!=42 or row['numerical'] is not None or not contract.exact(value,dict(status='rejected',reason='duplicate_unload')):raise ValueError('lifetime no-unload not detected')
    else:
        valid=contract.validate_runtime if kind=='runtime' else contract.validate_driver
        if row['exit_code']!=0 or not valid(value,seed,cycles,mode):raise ValueError('lifetime raw completion/omission mismatch')
        numerical=valid(value,seed,cycles,'positive')
        if type(row['numerical']) is not bool or row['numerical']!=numerical or numerical!=(mode=='positive'):raise ValueError('lifetime numerical mismatch')

def observe(folder,files,kind,mode,seed,cycles):
    verify_files(folder,files);bundle=folder/'resource-lifetime-runs'/uuid.uuid4().hex;bundle.mkdir(parents=True)
    wanted=payloads(files,kind,mode)
    for name in wanted:
        source={'nvcuda.dll':'ct_cuda.dll' if mode=='positive' else 'lifetime-'+mode+'.dll','cudart64_12.dll':'lifetime-runtime.dll','ct_underlying.dll':'ct_cuda.dll','vector.ptx':'vector-lifetime.ptx'}.get(name,name)
        shutil.copyfile(folder/source,bundle/name)
    args=argv(bundle,kind,seed,cycles)
    result=subprocess.run(args,cwd=bundle,capture_output=True,timeout=180)
    (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr)
    row=dict(kind=kind,mode=mode,seed=seed,cycles=cycles,bundle=bundle.relative_to(folder).as_posix(),command=args,files=wanted,
             observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')},exit_code=result.returncode,numerical=None if mode=='noop_unload' else mode=='positive')
    verify_run(folder,files,row);return row

def check_runs(folder,files,rows):
    if type(rows) is not list or any(type(r) is not dict for r in rows) or [(r.get('kind'),r.get('mode'),r.get('seed'),r.get('cycles')) for r in rows]!=list(SCENARIOS):raise ValueError('lifetime run set differs')
    for row in rows:verify_run(folder,files,row)

def audit(path):
    path=Path(path).resolve();folder=path.parent;m=json.loads(path.read_bytes())
    if (not folder.is_relative_to(ROOT/'.cache/runtime-attribute-runs') or set(m)!={'schema_version','scope','release_claim','source_fingerprint','parent_sha256','case_profile','commands','files','runs'}
            or type(m['schema_version']) is not int or m['schema_version']!=1 or m['scope']!=SCOPE or m['release_claim'] is not False or not contract.exact(m['case_profile'],PROFILE)):raise ValueError('lifetime capture scope')
    if m['source_fingerprint']!=source_fingerprint(ROOT):raise ValueError('lifetime source drift')
    parent=folder/'matrix-rounding-manifest.json'
    if digest(parent)!=m['parent_sha256']:raise ValueError('lifetime parent drift')
    audit_parent(parent)
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base=json.loads(producer.read_bytes())
    if m['commands']!=recipes(folder,producer,base) or type(m['files']) is not dict or set(m['files'])!=FILES:raise ValueError('lifetime recipe/files scope')
    verify_files(folder,m['files'])
    if m['files']['ct_cuda.dll']!=json.loads(parent.read_bytes())['files']['ct_cuda.dll'] or digest(folder/'lifetime-runtime.dll')!=digest(folder/'matrix-runtime-original.dll'):raise ValueError('lifetime parent providers')
    if (folder/'lifecycle-driver.def').read_text()!='EXPORTS\n'+'\n'.join(sorted(expected_exports(ROOT)))+'\n':raise ValueError('lifetime exports')
    if digest(folder/'lifecycle.cu')!=digest(ROOT/'tests/fixtures/lifecycle_runtime.cu') or digest(folder/'vector-lifetime.ptx')!=digest(ROOT/'tests/fixtures/vector_add.ptx'):raise ValueError('lifetime copied source')
    if ptx_tokens(payload(folder/'keep-lifecycle/lifecycle.fatbin'))!=ptx_tokens((folder/'keep-lifecycle/lifecycle.ptx').read_bytes()):raise ValueError('lifetime producer payload mismatch')
    check_runs(folder,m['files'],m['runs']);return m

def build(validator):
    parent=build_parent(validator);folder=parent.parent;fp=source_fingerprint(ROOT)
    if json.loads(parent.read_bytes())['source_fingerprint']!=fp:raise ValueError('lifetime parent source differs')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder)
    shutil.copyfile(folder/'matrix-runtime-original.dll',folder/'lifetime-runtime.dll');shutil.copyfile(ROOT/'tests/fixtures/lifecycle_runtime.cu',folder/'lifecycle.cu');shutil.copyfile(ROOT/'tests/fixtures/vector_add.ptx',folder/'vector-lifetime.ptx')
    (folder/'keep-lifecycle').mkdir();(folder/'lifecycle-driver.def').write_text('EXPORTS\n'+'\n'.join(sorted(expected_exports(ROOT)))+'\n')
    commands=recipes(folder,producer,base)
    for label,args in commands.items():command(args,folder,env,'lifetime-'+label)
    files={n:digest(folder/n) for n in FILES}
    rows=[observe(folder,files,*case) for case in SCENARIOS]
    if source_fingerprint(ROOT)!=fp:raise ValueError('lifetime source changed')
    path=folder/'resource-lifetime-manifest.json';path.write_text(json.dumps(dict(schema_version=1,scope=SCOPE,release_claim=False,source_fingerprint=fp,parent_sha256=digest(parent),case_profile=PROFILE,commands=commands,files=files,runs=rows),indent=2)+'\n')
    audit(path);(ROOT/'.cache/resource-lifetime-latest.json').write_text(json.dumps(dict(manifest=path.relative_to(ROOT).as_posix()))+'\n');return path

def replay(path):
    m=audit(path);path=Path(path).resolve();folder=path.parent;sha=digest(path)
    rows=[observe(folder,m['files'],*case) for case in SCENARIOS];check_runs(folder,m['files'],rows)
    if any(a['observations']!=b['observations'] or a['exit_code']!=b['exit_code'] for a,b in zip(m['runs'],rows)):raise ValueError('lifetime deterministic replay differs')
    audit(path)
    if digest(path)!=sha or source_fingerprint(ROOT)!=m['source_fingerprint']:raise ValueError('lifetime replay drift')
    report=folder/('resource-lifetime-replay-'+uuid.uuid4().hex+'.json');report.write_text(json.dumps(dict(manifest_sha256=sha,source_fingerprint=m['source_fingerprint'],release_claim=False,runs=rows),indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group();g.add_argument('--audit',type=Path);g.add_argument('--replay',type=Path)
    p.add_argument('--validator',type=Path,default=ROOT/'.cache/universal-foundation/spirv-build/tools/Release/spirv-val.exe');args=p.parse_args()
    if sys.flags.optimize:raise ValueError('unoptimized lifetime verification required')
    if args.audit:path=args.audit;audit(path)
    elif args.replay:path=replay(args.replay)
    else:path=build(args.validator)
    print(json.dumps(dict(status='pass',scope=SCOPE,record=path.resolve().relative_to(ROOT).as_posix(),release_claim=False)))
