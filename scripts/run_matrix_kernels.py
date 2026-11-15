"""Execute unchanged pinned original matrix kernels, never the original EXE."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import uuid
from run_fma import build as build_parent
from run_upstream_vectoradd import build as build_vector,replay as replay_vector,check_set as check_vector_runs
from triage_matrixmul import build as build_triage,audit as audit_triage
from run_relaxed_nvcc import digest,verify_files
from run_validation import source_fingerprint
from matrix_kernel_check import CASES,input_files,input_buffers,validate_case,validate_report,omission_matches,entry_map,exact,seed_value
import matrix_kernel_check as BASELINE
from validate_spirv import run_validator
ROOT=Path(__file__).resolve().parents[1]
MODES=('positive','positive','noop_launch','noop_copy')
PROVIDERS={'positive':'ct_cuda.dll','noop_launch':'host-noop.dll','noop_copy':'copy-noop.dll'}

def worker_flags(contract):
    import matrix_breadth_check as breadth
    import matrix_rounding_check as rounding
    if contract is BASELINE:return []
    if contract is breadth:return ['--breadth-v1']
    if contract is rounding:return ['--rounding-v1']
    raise ValueError('unknown matrix worker contract')

def verify_run(folder,files,row,*,contract=BASELINE):
    flags=worker_flags(contract)
    CASES,input_files,validate_case,validate_report,omission_matches=(getattr(contract,n) for n in ('CASES','input_files','validate_case','validate_report','omission_matches'))
    if type(row) is not dict or set(row)!={'mode','seed','bundle','command','files','outputs','exit_code','numerical'} or row['mode'] not in PROVIDERS:raise ValueError('matrix run schema')
    seed_value(row['seed']);mode=row['mode'];name=row['bundle']
    if type(name) is not str or Path(name).is_absolute():raise ValueError('matrix bundle name')
    bundle=(folder/name).resolve()
    if not bundle.is_relative_to((folder/'matrix-kernel-runs').resolve()):raise ValueError('matrix bundle escape')
    wanted={'nvcuda.dll':files[PROVIDERS[mode]],'matrix.ptx':files['matrix.ptx']}
    if mode!='positive':wanted['ct_underlying.dll']=files['ct_cuda.dll']
    data=input_files(row['seed']);wanted.update({n:hashlib.sha256(blob).hexdigest() for n,blob in data.items()})
    job=dict(schema_version=getattr(contract,'JOB_SCHEMA',1),seed=row['seed'],files=wanted)
    if not exact(json.loads((bundle/'job.json').read_bytes()),job):raise ValueError('matrix job identity differs')
    wanted['job.json']=digest(bundle/'job.json')
    if not exact(row['files'],wanted):raise ValueError('matrix run payload identities')
    verify_files(bundle,row['files'])
    outputs={f'case-{i}-{k}-readback.bin' for i in range(len(CASES)) for k in ('a','b','c')}|{'stdout.json','stderr.txt'}
    if type(row['outputs']) is not dict or set(row['outputs'])!=outputs:raise ValueError('matrix observations incomplete')
    if {p.name for p in bundle.iterdir()}!=set(row['files'])|outputs:raise ValueError('unrecorded matrix bundle artifacts')
    verify_files(bundle,row['outputs'])
    command=[sys.executable,str(ROOT/'scripts/matrix_kernel_worker.py')]+flags+[str(bundle/'job.json')]
    if row['command']!=command or type(row['exit_code']) is not int or row['exit_code']!=0 or (bundle/'stderr.txt').read_bytes():raise ValueError('matrix API path did not complete')
    report=json.loads((bundle/'stdout.json').read_bytes())
    if not validate_report(report,row['seed']):raise ValueError('matrix API report invalid')
    numerical=[]
    for i,case in enumerate(CASES):
        inputs={k:(bundle/f'case-{i}-{k}.bin').read_bytes() for k in ('a','b','c')}
        back={k:(bundle/f'case-{i}-{k}-readback.bin').read_bytes() for k in ('a','b','c')}
        valid=validate_case(row['seed'],case,inputs,back);numerical.append(valid)
        if mode!='positive' and not omission_matches(mode,inputs,back):raise ValueError('matrix omission signature differs')
    if not exact(row['numerical'],numerical) or numerical!=[mode=='positive']*len(CASES):raise ValueError('matrix numerical acceptance differs')
    return report

def observe(folder,files,mode,seed,*,contract=BASELINE):
    flags=worker_flags(contract)
    CASES,input_files=(getattr(contract,n) for n in ('CASES','input_files'))
    verify_files(folder,files);bundle=folder/'matrix-kernel-runs'/uuid.uuid4().hex;bundle.mkdir(parents=True)
    shutil.copyfile(folder/PROVIDERS[mode],bundle/'nvcuda.dll');shutil.copyfile(folder/'matrix.ptx',bundle/'matrix.ptx')
    if mode!='positive':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
    for name,data in input_files(seed).items():(bundle/name).write_bytes(data)
    pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
    (bundle/'job.json').write_text(json.dumps(dict(schema_version=getattr(contract,'JOB_SCHEMA',1),seed=seed,files=pins),indent=2)+'\n');pins=dict(pins,**{'job.json':digest(bundle/'job.json')})
    command=[sys.executable,str(ROOT/'scripts/matrix_kernel_worker.py')]+flags+[str(bundle/'job.json')]
    result=subprocess.run(command,cwd=bundle,capture_output=True,timeout=60)
    (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr)
    verify_files(bundle,pins)
    names=[f'case-{i}-{k}-readback.bin' for i in range(len(CASES)) for k in ('a','b','c')]+['stdout.json','stderr.txt']
    outputs={n:digest(bundle/n) for n in names}
    row=dict(mode=mode,seed=seed,bundle=bundle.relative_to(folder).as_posix(),command=command,files=pins,outputs=outputs,exit_code=result.returncode,numerical=[mode=='positive']*len(CASES))
    verify_run(folder,files,row,contract=contract);verify_files(folder,files)
    return row

def check_runs(folder,files,rows):
    if type(rows) is not list or any(type(r) is not dict for r in rows) or [r.get('mode') for r in rows]!=list(MODES) or len({r.get('seed') for r in rows})!=4:raise ValueError('matrix run set differs')
    reports=[verify_run(folder,files,row) for row in rows]
    if any((r['adapter'],r['limits'])!=(reports[0]['adapter'],reports[0]['limits']) for r in reports):raise ValueError('matrix device changed')

def audit(path):
    path=Path(path).resolve();folder=path.parent
    if not folder.is_relative_to(ROOT/'.cache/runtime-attribute-runs'):raise ValueError('matrix capture escape')
    m=json.loads(path.read_bytes())
    if (set(m)!={'schema_version','scope','release_claim','source_fingerprint','parent_manifest_sha256','references','files','entries','validator','runs'}
            or type(m['schema_version']) is not int or m['schema_version']!=1 or m['scope']!='diagnostic_original_matrix_kernels' or m['release_claim'] is not False):raise ValueError('matrix capture schema')
    if m['source_fingerprint']!=source_fingerprint(ROOT):raise ValueError('matrix source drift')
    parent=folder/'fma-manifest.json';parent_data=json.loads(parent.read_bytes())
    if digest(parent)!=m['parent_manifest_sha256'] or parent_data['source_fingerprint']!=m['source_fingerprint'] or parent_data['scope']!='diagnostic_fused_f32':raise ValueError('matrix parent identity differs')
    verify_files(folder,parent_data['files']);verify_files(folder,m['files'])
    if set(m['files'])!={'ct_cuda.dll','host-noop.dll','copy-noop.dll','matrix.ptx','matrix.spv'} or m['files']['ct_cuda.dll']!=parent_data['files']['ct_cuda.dll']:raise ValueError('matrix provider set differs')
    if not exact(m['entries'],{str(t):n for t,n in entry_map((folder/'matrix.ptx').read_bytes()).items()}):raise ValueError('matrix entry identity differs')
    if type(m['references']) is not dict or set(m['references'])!={'vector','vector_replay','matrix'}:raise ValueError('matrix references missing')
    references={}
    for role,prefix in (('vector','upstream-vectoradd-runs'),('vector_replay','upstream-vectoradd-runs'),('matrix','matrixmul-triage')):
        ref=m['references'][role]
        if type(ref) is not dict or set(ref)!={'path','sha256'} or not isinstance(ref['path'],str) or Path(ref['path']).is_absolute():raise ValueError('matrix reference schema')
        target=(ROOT/ref['path']).resolve()
        if not target.is_relative_to(ROOT/'.cache'/prefix) or digest(target)!=ref['sha256']:raise ValueError('matrix reference drift')
        references[role]=target
    triage,vector_folder=audit_triage(references['matrix'])
    if vector_folder!=references['vector'].parent or references['vector_replay'].parent!=vector_folder:raise ValueError('matrix vector reference differs')
    vector=json.loads(references['vector'].read_bytes());replayed=json.loads(references['vector_replay'].read_bytes())
    if (set(replayed)!={'manifest_sha256','release_claim','runs','independent_driver'} or replayed['manifest_sha256']!=digest(references['vector'])
            or replayed['release_claim'] is not False or not exact(replayed['independent_driver'],vector['independent_driver'])):raise ValueError('vector replay reference invalid')
    check_vector_runs(vector_folder,vector['files'],replayed['runs'])
    if (triage['diagnostic']['offline_ptx']['status']!='translated'
            or triage['files']['keep/matrixMul.ptx']!=m['files']['matrix.ptx']
            or triage['diagnostic']['offline_ptx']['module_sha256']!=m['files']['matrix.spv']):raise ValueError('matrix producer/translation correspondence differs')
    validator=m['validator'];lock=next(t for t in json.loads((ROOT/'docs/compatibility/toolchain-lock-v1.json').read_bytes())['tools'] if t['id']=='spirv-val')
    if not exact(validator,dict(status='pass',reason='passed',module_sha256=m['files']['matrix.spv'],tool_sha256=lock['files']['spirv-val.exe'])):raise ValueError('matrix validator evidence differs')
    check_runs(folder,m['files'],m['runs']);return m

def build(validator):
    if sys.flags.optimize:raise ValueError('matrix checks require unoptimized Python')
    parent=build_parent(validator);folder=parent.parent;fp=source_fingerprint(ROOT)
    if json.loads(parent.read_bytes())['source_fingerprint']!=fp:raise ValueError('matrix parent source differs')
    vector,_=build_vector();_,vector_replay=replay_vector(vector)
    (ROOT/'.cache/upstream-vectoradd-latest.json').write_text(json.dumps(dict(manifest=vector.relative_to(ROOT).as_posix()))+'\n')
    matrix,m=build_triage();ptx=matrix.parent/'keep/matrixMul.ptx';spirv=matrix.parent/m['observations']['directory']/'translated.spv'
    entry_map(ptx.read_bytes());shutil.copyfile(ptx,folder/'matrix.ptx');shutil.copyfile(spirv,folder/'matrix.spv')
    lock=next(t for t in json.loads((ROOT/'docs/compatibility/toolchain-lock-v1.json').read_bytes())['tools'] if t['id']=='spirv-val')
    checked=run_validator(folder/'matrix.spv',validator,lock,required=True)
    if checked['status']!='pass':raise ValueError('matrix validator failed')
    files={n:digest(folder/n) for n in ('ct_cuda.dll','host-noop.dll','copy-noop.dll','matrix.ptx','matrix.spv')}
    rows=[];seeds=set()
    for mode in MODES:
        if source_fingerprint(ROOT)!=fp:raise ValueError('matrix source changed before dispatch')
        seed=secrets.randbelow(1000000)+1
        while seed in seeds:seed=secrets.randbelow(1000000)+1
        seeds.add(seed);rows.append(observe(folder,files,mode,seed))
    if source_fingerprint(ROOT)!=fp:raise ValueError('matrix source changed')
    target=folder/'matrix-kernel-manifest.json';target.write_text(json.dumps(dict(schema_version=1,scope='diagnostic_original_matrix_kernels',release_claim=False,source_fingerprint=fp,parent_manifest_sha256=digest(parent),references={role:dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p)) for role,p in (('vector',vector),('vector_replay',vector_replay),('matrix',matrix))},files=files,entries={str(t):n for t,n in entry_map(ptx.read_bytes()).items()},validator=checked,runs=rows),indent=2)+'\n')
    audit(target);(ROOT/'.cache/matrix-kernel-latest.json').write_text(json.dumps(dict(manifest=target.relative_to(ROOT).as_posix()))+'\n');return target

def replay(path):
    if sys.flags.optimize:raise ValueError('matrix checks require unoptimized Python')
    path=Path(path).resolve();m=audit(path);sha=digest(path);folder=path.parent
    rows=[observe(folder,m['files'],old['mode'],old['seed']) for old in m['runs']];check_runs(folder,m['files'],rows)
    for old,new in zip(m['runs'],rows):
        if old['mode']=='positive' and old['outputs']!={n:s for n,s in new['outputs'].items()}:
            # API/device report and all exact raw buffers must replay identically.
            raise ValueError('matrix deterministic replay differs')
    if sha!=digest(path) or source_fingerprint(ROOT)!=m['source_fingerprint']:raise ValueError('matrix replay drift')
    audit(path)
    report=folder/('matrix-kernel-replay-'+uuid.uuid4().hex+'.json');report.write_text(json.dumps(dict(manifest_sha256=sha,source_fingerprint=m['source_fingerprint'],release_claim=False,runs=rows),indent=2)+'\n');return m,report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);group=p.add_mutually_exclusive_group();group.add_argument('--audit',type=Path);group.add_argument('--replay',type=Path)
    p.add_argument('--validator',type=Path,default=ROOT/'.cache/universal-foundation/spirv-build/tools/Release/spirv-val.exe');args=p.parse_args();report=None
    if args.audit:path=args.audit;audit(path)
    elif args.replay:path=args.replay;_,report=replay(path)
    else:path=build(args.validator)
    print(json.dumps(dict(status='pass',scope='diagnostic_original_matrix_kernels',manifest=Path(path).resolve().relative_to(ROOT).as_posix(),replay=None if report is None else report.relative_to(ROOT).as_posix(),execution_performed=not bool(args.audit),original_application_execution_performed=False,release_claim=False)))
