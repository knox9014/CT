"""Actual CT experimental virtual target: no metadata-injection DLL in product runs."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from run_matrix_runtime import build as build_parent,audit as audit_parent,argv_for
from run_relaxed_nvcc import digest,verify_files,command,host_environment
from run_validation import source_fingerprint
from check_compatibility_profile import expected_exports
from matrix_runtime_check import SHAPES,exact
from virtual_target_check import TARGET,QUALIFICATION,ABI_MODES,abi_valid,qualification_valid,app_valid
from topology_attribute_check import TOPOLOGY_POLICY

ROOT=Path(__file__).resolve().parents[1]
PROFILE='docs/compatibility/virtual-target-v1.json'
APP_CASES=(('strict',SHAPES[0]),('invalid_config',SHAPES[0]),('nominal',SHAPES[0]),('nominal',SHAPES[1]),('trace',SHAPES[0]),('trace',SHAPES[1]),('noop_launch',SHAPES[1]),('noop_copy',SHAPES[1]))
ABI_CASES=tuple((m,m) for m in ABI_MODES)+tuple(('loader_'+m,'loader') for m in ('missing','forwarded','absent'))
INPUTS=('scripts/run_virtual_target.py','scripts/virtual_target_check.py','tests/virtual_target_native_abi.cpp','tests/test_virtual_target.py','tests/matrix_runtime_trace.c',PROFILE)
FILES={'ct_cuda.dll','matrix-runtime-original.dll','matrixMul.exe','virtual-abi.exe','virtual-trace.dll','virtual-noop_launch.dll','virtual-noop_copy.dll','missing.dll','forwarded.dll','foreign.dll'}

def environment(value=None):
    env={k:v for k,v in os.environ.items() if k.upper()!='CT_VIRTUAL_TARGET'}
    if value is not None:env['CT_VIRTUAL_TARGET']=value
    return env

def profile():
    p=json.loads((ROOT/PROFILE).read_bytes())
    if not exact(p.get('topology_count'),TOPOLOGY_POLICY):raise ValueError('virtual topology contract')
    if (type(p['schema_version']) is not int or p['schema_version']!=1
            or p['id']!=TARGET or p['experimental'] is not True or p['release_claim'] is not False
            or p['opt_in']['environment']!='CT_VIRTUAL_TARGET' or p['opt_in']['value']!=TARGET
            or p['opt_in']['immutable_for_process'] is not True or p['opt_in']['default']!='strict'
            or not exact(p['compute_capability'],dict(major=5,minor=2,meaning='virtual PTX selection target, not NVIDIA hardware or conformance'))
            or p['accepted_ptx_pairs']!=['7.0/sm_50','8.0/sm_52']):raise ValueError('virtual profile identity/semantics')
    pairs=next(f for f in json.loads((ROOT/'docs/compatibility/profile-v1.json').read_bytes())['features'] if f['id']=='ptx.module')['limits']['profiles']
    if p['accepted_ptx_pairs']!=pairs:raise ValueError('virtual profile PTX drift')
    if p['api_contracts']!=['docs/compatibility/profile-v1.json','docs/compatibility/runtime-profile-v1.json']:raise ValueError('virtual contract reference')
    return p

def recipes(folder,producer,base):
    cl=base['host']['tools']['cl.exe']['path']
    rows={'virtual-abi':[cl,'/nologo','/utf-8','/W4','/WX','/EHsc','/std:c++17','/I'+str(producer.parent/'toolkit/include'),str(ROOT/'tests/virtual_target_native_abi.cpp'),'/Fo'+str(folder/'virtual-abi.obj'),'/Fe'+str(folder/'virtual-abi.exe')]}
    for mode in ('trace','noop_launch','noop_copy'):
        args=[cl,'/nologo','/utf-8','/W4','/WX','/LD','/D_CRT_SECURE_NO_WARNINGS','/DMATRIX_PRODUCT_TARGET']
        if mode=='noop_launch':args+=['/DMATRIX_NO_LAUNCH']
        if mode=='noop_copy':args+=['/DMATRIX_NO_COPY']
        rows[mode]=args+[str(ROOT/'tests/matrix_runtime_trace.c'),'/Fo'+str(folder/('virtual-'+mode+'.obj')),'/Fe'+str(folder/('virtual-'+mode+'.dll')),'/link','/DEF:'+str(folder/'virtual-trace.def')]
    return rows

def abi_payloads(files,case):
    wanted={'virtual-abi.exe':files['virtual-abi.exe'],'cudart64_12.dll':files['matrix-runtime-original.dll']}
    if case=='loader_absent':return wanted
    if case.startswith('loader_'):
        provider=case.removeprefix('loader_')+'.dll';wanted.update({'nvcuda.dll':files[provider],'ct_underlying.dll':files['ct_cuda.dll']})
        if case=='loader_forwarded':wanted['foreign.dll']=files['foreign.dll']
    else:wanted['nvcuda.dll']=files['ct_cuda.dll']
    return wanted

def app_payloads(files,mode):
    wanted={'matrixMul.exe':files['matrixMul.exe'],'cudart64_12.dll':files['matrix-runtime-original.dll']}
    if mode in ('strict','invalid_config','nominal'):wanted['nvcuda.dll']=files['ct_cuda.dll']
    else:wanted.update({'nvcuda.dll':files['virtual-'+mode+'.dll'],'ct_underlying.dll':files['ct_cuda.dll']})
    return wanted

def bundle_at(folder,name,subdir):
    if type(name) is not str or Path(name).is_absolute():raise ValueError('virtual bundle name')
    path=(folder/name).resolve()
    if not path.is_relative_to(folder/subdir):raise ValueError('virtual bundle escape')
    return path

def check_abi(folder,files,row):
    if type(row) is not dict or set(row)!={'case','mode','bundle','payloads','command','observations','exit_code','result'} or (row['case'],row['mode']) not in ABI_CASES:raise ValueError('virtual ABI schema')
    bundle=bundle_at(folder,row['bundle'],'virtual-abi-runs');wanted=abi_payloads(files,row['case'])
    if row['payloads']!=wanted or set(row['observations'])!={'stdout.json','stderr.txt'} or {p.name for p in bundle.iterdir()}!=set(wanted)|set(row['observations']):raise ValueError('virtual ABI artifacts')
    verify_files(bundle,wanted);verify_files(bundle,row['observations'])
    argv=[str(bundle/'virtual-abi.exe'),str(bundle/'cudart64_12.dll'),str(bundle/'nvcuda.dll'),row['mode']]
    if row['command']!=argv or type(row['exit_code']) is not int or row['exit_code']!=0 or (bundle/'stderr.txt').read_bytes():raise ValueError('virtual ABI did not complete')
    value=json.loads((bundle/'stdout.json').read_bytes())
    if not exact(row['result'],value) or not abi_valid(row['mode'],value):raise ValueError('virtual ABI result invalid')

def check_app(folder,files,row):
    if type(row) is not dict or set(row)!={'mode','shape','bundle','payloads','command','policy_environment','observations','exit_code'}:raise ValueError('virtual app schema')
    if type(row['shape']) is not list or any(type(v) is not int for v in row['shape']):raise ValueError('virtual shape type')
    mode=row['mode'];shape=tuple(row['shape'])
    if (mode,shape) not in APP_CASES:raise ValueError('virtual app case')
    bundle=bundle_at(folder,row['bundle'],'virtual-app-runs');wanted=app_payloads(files,mode)
    env=None if mode=='strict' else 'typo' if mode=='invalid_config' else TARGET
    if row['command']!=argv_for(bundle,shape) or row['policy_environment']!=env or row['payloads']!=wanted:raise ValueError('virtual app command/configuration')
    names={'stdout.bin','stderr.bin'};traced=mode in ('trace','noop_launch','noop_copy')
    if traced:names|={'input-a.bin','input-b.bin','output.bin','trace.json'}
    if set(row['observations'])!=names or {p.name for p in bundle.iterdir()}!=set(wanted)|names:raise ValueError('virtual app artifacts; metadata injection forbidden')
    verify_files(bundle,wanted);verify_files(bundle,row['observations'])
    values=[(bundle/n).read_bytes() for n in ('stdout.bin','stderr.bin')]
    if traced:values += [(bundle/n).read_bytes() for n in ('input-a.bin','input-b.bin','output.bin')]+[json.loads((bundle/'trace.json').read_bytes())]
    if not app_valid(mode,shape,row['exit_code'],*values):raise ValueError('virtual app external oracle failed')

def copy_payloads(folder,bundle,wanted,files):
    for dst,sha in wanted.items():
        # Aliases are resolved by hash from a closed captured provider table.
        choices=[folder/n for n,pinned in files.items() if pinned==sha]
        if not choices:raise ValueError('virtual provider absent')
        shutil.copyfile(choices[0],bundle/dst)
    verify_files(bundle,wanted)

def observe_abi(folder,files,case,mode):
    verify_files(folder,files);bundle=folder/'virtual-abi-runs'/uuid.uuid4().hex;bundle.mkdir(parents=True)
    wanted=abi_payloads(files,case);copy_payloads(folder,bundle,wanted,files)
    argv=[str(bundle/'virtual-abi.exe'),str(bundle/'cudart64_12.dll'),str(bundle/'nvcuda.dll'),mode]
    result=subprocess.run(argv,cwd=bundle,env=environment(),capture_output=True,timeout=60)
    (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr)
    row=dict(case=case,mode=mode,bundle=bundle.relative_to(folder).as_posix(),payloads=wanted,command=argv,observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')},exit_code=result.returncode,result=json.loads(result.stdout) if result.stdout else None)
    (folder/'last-virtual-abi.json').write_text(json.dumps(row,indent=2)+'\n');check_abi(folder,files,row);verify_files(folder,files);return row

def observe_app(folder,files,mode,shape):
    verify_files(folder,files);bundle=folder/'virtual-app-runs'/uuid.uuid4().hex;bundle.mkdir(parents=True)
    wanted=app_payloads(files,mode);copy_payloads(folder,bundle,wanted,files);argv=argv_for(bundle,shape)
    policy=None if mode=='strict' else 'typo' if mode=='invalid_config' else TARGET
    result=subprocess.run(argv,cwd=bundle,env=environment(policy),capture_output=True,timeout=60)
    (bundle/'stdout.bin').write_bytes(result.stdout);(bundle/'stderr.bin').write_bytes(result.stderr)
    row=dict(mode=mode,shape=list(shape),bundle=bundle.relative_to(folder).as_posix(),payloads=wanted,command=argv,policy_environment=policy,observations={p.name:digest(p) for p in bundle.iterdir() if p.name not in wanted},exit_code=result.returncode)
    (folder/'last-virtual-app.json').write_text(json.dumps(row,indent=2)+'\n');check_app(folder,files,row);verify_files(folder,files);return row

def check_runs(folder,files,abis,apps):
    if type(abis) is not list or [(r['case'],r['mode']) for r in abis]!=list(ABI_CASES):raise ValueError('virtual ABI case set')
    if type(apps) is not list or [(r['mode'],tuple(r['shape'])) for r in apps]!=list(APP_CASES):raise ValueError('virtual app case set')
    for r in abis:check_abi(folder,files,r)
    for r in apps:check_app(folder,files,r)

def audit(path):
    path=Path(path).resolve();folder=path.parent;m=json.loads(path.read_bytes());profile()
    if not folder.is_relative_to(ROOT/'.cache/runtime-attribute-runs') or set(m)!={'schema_version','scope','qualification','source_fingerprint','inputs','parent_sha256','commands','files','abi_runs','app_runs'} or type(m['schema_version']) is not int or m['schema_version']!=1 or m['scope']!='experimental_product_virtual_target' or not qualification_valid(m['qualification']):raise ValueError('virtual manifest scope')
    if m['source_fingerprint']!=source_fingerprint(ROOT) or m['inputs']!={n:digest(ROOT/n) for n in INPUTS}:raise ValueError('virtual source drift')
    parent=folder/'matrix-runtime-manifest.json'
    if digest(parent)!=m['parent_sha256']:raise ValueError('virtual parent drift')
    p=audit_parent(parent);attribute=json.loads((folder/'manifest.json').read_bytes())
    if set(m['files'])!=FILES or any(m['files'][n]!=p['files'][n] for n in ('ct_cuda.dll','matrix-runtime-original.dll','matrixMul.exe')) or any(m['files'][n]!=attribute['files'][n] for n in ('missing.dll','forwarded.dll','foreign.dll')):raise ValueError('virtual parent provider identities')
    base=json.loads((ROOT/'.cache/p09a2-producer/manifest.json').read_bytes())
    if m['commands']!=recipes(folder,ROOT/'.cache/p09a2-producer/manifest.json',base):raise ValueError('virtual build recipe drift')
    verify_files(folder,m['files']);check_runs(folder,m['files'],m['abi_runs'],m['app_runs']);return m

def build(validator):
    # All parent diagnostics run strict, regardless of the caller's inherited setting.
    os.environ.pop('CT_VIRTUAL_TARGET',None);profile()
    parent=build_parent(validator);folder=parent.parent;fp=source_fingerprint(ROOT)
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder)
    (folder/'virtual-trace.def').write_text('EXPORTS\n'+'\n'.join(sorted(expected_exports(ROOT)))+'\n')
    commands=recipes(folder,producer,base)
    for label,argv in commands.items():command(argv,folder,env,label)
    files={n:digest(folder/n) for n in FILES}
    abis=[observe_abi(folder,files,c,m) for c,m in ABI_CASES]
    apps=[observe_app(folder,files,m,s) for m,s in APP_CASES]
    if fp!=source_fingerprint(ROOT):raise ValueError('virtual source changed')
    path=folder/'virtual-target-manifest.json';path.write_text(json.dumps(dict(schema_version=1,scope='experimental_product_virtual_target',qualification=QUALIFICATION,source_fingerprint=fp,inputs={n:digest(ROOT/n) for n in INPUTS},parent_sha256=digest(parent),commands=commands,files=files,abi_runs=abis,app_runs=apps),indent=2)+'\n')
    audit(path);(ROOT/'.cache/virtual-target-latest.json').write_text(json.dumps(dict(manifest=path.relative_to(ROOT).as_posix()))+'\n');return path

def replay(path):
    m=audit(path);folder=path.resolve().parent;sha=digest(path)
    abis=[observe_abi(folder,m['files'],r['case'],r['mode']) for r in m['abi_runs']]
    apps=[observe_app(folder,m['files'],r['mode'],tuple(r['shape'])) for r in m['app_runs']];check_runs(folder,m['files'],abis,apps)
    for old,new in zip(m['app_runs'],apps):
        for n in ('input-a.bin','input-b.bin','output.bin','trace.json') if old['mode'] in ('trace','noop_launch','noop_copy') else ():
            if old['observations'][n]!=new['observations'][n]:raise ValueError('virtual deterministic replay differs')
    for old,new in zip(m['abi_runs'],abis):
        if not exact(old['result'],new['result']):raise ValueError('virtual ABI replay differs')
    audit(path)
    if digest(path)!=sha:raise ValueError('virtual manifest changed')
    saved=folder/('virtual-target-replay-'+uuid.uuid4().hex+'.json');saved.write_text(json.dumps(dict(manifest_sha256=sha,qualification=QUALIFICATION,abi_runs=abis,app_runs=apps),indent=2)+'\n');return saved

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group();g.add_argument('--audit',type=Path);g.add_argument('--replay',type=Path)
    p.add_argument('--validator',type=Path,default=ROOT/'.cache/universal-foundation/spirv-build/tools/Release/spirv-val.exe');args=p.parse_args()
    if sys.flags.optimize:raise ValueError('unoptimized verification required')
    if args.audit:path=args.audit;audit(path)
    elif args.replay:path=replay(args.replay)
    else:path=build(args.validator)
    print(json.dumps(dict(status='pass',record=path.resolve().relative_to(ROOT).as_posix(),qualification=QUALIFICATION)))
