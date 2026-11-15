"""Independent numerical oracle and bound evidence for real nvcc executables."""
import argparse
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from ct import inspect_pe,prepare_bundle
from prepare_nvcc_probe import audit_probe,digest
from run_validation import source_fingerprint

MODES=('single','repeat','ordinary','two_contexts','parallel','multi_module','boundaries','retire','noop')
INPUTS=['tests/fixtures/p09a2/'+s for s in ('kernel_oracle.cu','module_a.cu','module_b.cu')]+[
    'include/ct_cuda.h','tests/p09a_noop_driver.c','tests/p09a_driver_control.def',
    'scripts/run_p09a2_smoke.ps1','tests/p09a2_kernel_check.py','tests/p09a2_kernel_control.cpp','include/ct_cudart.h']
ROLES={'application':'host.exe','driver':'ct_cuda.dll','runtime':'ct_cudart.dll','noop':'noop.dll','control':'control.exe','image':'kernel_oracle.fatbin'}
BOUNDARY_ERRORS=[9,9,801,1,98]


def verify_result(value,seed,mode):
    try:
        if mode not in MODES or type(seed)is not int or not 1<=seed<=1000000:return ['invalid invocation']
        canonical='single' if mode=='noop' else mode
        if set(value)!={'seed','mode','errors','runs'} or value['seed']!=seed or value['mode']!=canonical:return ['result identity mismatch']
        if value['errors']!=(BOUNDARY_ERRORS if canonical=='boundaries' else [98] if canonical=='retire' else []):return ['boundary errors mismatch']
        runs=value['runs'];count=8 if canonical=='parallel' else 3 if canonical=='two_contexts' else 1
        if not isinstance(runs,list) or len(runs)!=count:return ['native runs absent']
        for index,run in enumerate(runs):
            actual_seed=seed+index if count>1 else seed
            if set(run)!={'seed','a','b','c'} or run['seed']!=actual_seed:return ['run identity mismatch']
            expected_a=[0xdecafbad]*21;expected_b=expected_a.copy();expected_c=[0xa5a5a5a5]*21
            for i in range(17):
                a=(actual_seed*13+i*37)&0xffffffff;b=(actual_seed*17+i*19)&0xffffffff
                expected_a[i+2]=a;expected_b[i+2]=b
                expected_c[i+2]=((3*(a+5)+9) if canonical=='multi_module' else a+b if canonical=='retire' else a+b+7)&0xffffffff
            for name,expected in [('a',expected_a),('b',expected_b),('c',expected_c)]:
                observed=run[name]
                if not isinstance(observed,list) or len(observed)!=21 or any(type(x)is not int or not 0<=x<=0xffffffff for x in observed):return ['native arrays absent']
                if observed!=expected:return ['numerical/guard/input mismatch']
        return []
    except (TypeError,ValueError,KeyError):return ['invalid native result']


def local(root,name):
    p=(root/name).resolve()
    if not p.is_relative_to(root/'.cache/p09a2-kernel'):raise ValueError('artifact escape')
    return p


def audit_manifest(path,root=ROOT,*,execute=False):
    try:
        m=json.loads(Path(path).read_bytes())
        if set(m)!={'schema_version','case_id','source_tree','inputs','producer','artifacts','compiler_outputs','modes'} or m['schema_version']!=1 or m['case_id']!='arc.runtime_kernel':return ['kernel schema mismatch']
        if m['source_tree']!=source_fingerprint(root) or m['inputs']!={n:digest(root/n) for n in INPUTS}:return ['kernel source mismatch']
        producer=m['producer'];p=(root/producer['path']).resolve()
        if not p.is_relative_to(root/'.cache') or digest(p)!=producer['sha256'] or audit_probe(p):return ['kernel producer mismatch']
        if set(m['artifacts'])!=set(ROLES):return ['kernel artifacts absent']
        for role,item in m['artifacts'].items():
            if set(item)!={'path','sha256'}:return ['artifact schema']
            f=local(root,item['path'])
            if f.name!=ROLES[role] or digest(f)!=item['sha256']:return ['kernel artifact changed']
            if role!='image':inspect_pe(f.read_bytes(),dll=role not in ('application','control'),runtime=role=='application')
        imports=inspect_pe(local(root,m['artifacts']['application']['path']).read_bytes(),runtime=True)['imports']
        symbols={s for i in imports if i['library'].lower()=='cudart64_12.dll' for s in i['symbols']}
        if not {'cudaLaunchKernel','__cudaRegisterFatBinary','__cudaRegisterFunction','__cudaPushCallConfiguration','__cudaPopCallConfiguration'}<=symbols or '__cudaRegisterVar' in symbols:return ['genuine Runtime kernel imports absent']
        folder=local(root,m['artifacts']['application']['path']).parent
        required={f'keep/{name}{suffix}' for name in ('kernel_oracle','module_a','module_b') for suffix in ('.fatbin','.ptx','.cudafe1.stub.c')}
        if set(m['compiler_outputs'])!=required:return ['generated compiler outputs absent']
        for name,sha in m['compiler_outputs'].items():
            if digest(folder/name)!=sha:return ['compiler image/stub changed']
        if m['artifacts']['image']['sha256']!=m['compiler_outputs']['keep/kernel_oracle.fatbin']:return ['control image changed']
        for name in ('kernel_oracle.cu','module_a.cu','module_b.cu'):
            if digest(folder/name)!=m['inputs']['tests/fixtures/p09a2/'+name]:return ['compiled source changed']
        if digest(folder/'ct_cuda.h')!=m['inputs']['include/ct_cuda.h']:return ['compiled Driver declarations changed']
        if len(m['modes'])!=len(MODES) or {x['mode'] for x in m['modes']}!=set(MODES):return ['kernel modes absent']
        for item in m['modes']:
            if set(item)!={'mode','seed','exit_code','stdout','stderr','bundle','payloads'}:return ['kernel observation schema']
            mode=item['mode'];seed=item['seed'];bundle=local(root,item['bundle'])
            expected={('control.exe' if mode=='retire' else 'host.exe'):('control' if mode=='retire' else 'application'),'cudart64_12.dll':'runtime','nvcuda.dll':'noop' if mode=='noop' else 'driver'}
            if mode=='retire':expected['kernel_oracle.fatbin']='image'
            if mode=='noop':expected['ct_underlying.dll']='driver'
            if item['payloads']!=expected:return ['kernel bundle roles mismatch']
            for name,role in expected.items():
                if digest(bundle/name)!=m['artifacts'][role]['sha256']:return ['kernel bundle changed']
            out=local(root,item['stdout']);err=local(root,item['stderr'])
            if item['exit_code']!=0 or out.stat().st_size>65536 or err.read_bytes():return ['native execution failed']
            result=json.loads(out.read_bytes());errors=verify_result(result,seed,mode)
            if mode=='noop':
                if errors!=['numerical/guard/input mismatch'] or result['runs'][0]['c']!=[0xa5a5a5a5]*21:return ['no-op launch not detected']
            elif errors:return errors
            if execute:
                fresh=secrets.randbelow(999990)+1
                r=subprocess.run([str(bundle/('control.exe' if mode=='retire' else 'host.exe')),'single' if mode=='noop' else mode,str(fresh)],cwd=bundle,capture_output=True,timeout=120)
                if r.returncode or r.stderr:return ['kernel replay failed']
                replay=json.loads(r.stdout);errors=verify_result(replay,fresh,mode)
                if mode=='noop':
                    if errors!=['numerical/guard/input mismatch'] or replay['runs'][0]['c']!=[0xa5a5a5a5]*21:return ['replayed no-op not detected']
                elif errors:return errors
        if execute:return audit_manifest(path,root,execute=False)
        return []
    except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError):return ['kernel evidence unavailable or changed']


def capture(folder,producer):
    folder=folder.resolve();producer=producer.resolve()
    if not folder.is_relative_to(ROOT/'.cache/p09a2-kernel') or audit_probe(producer):raise ValueError('kernel inputs unavailable')
    artifacts={r:dict(path=(folder/n).relative_to(ROOT).as_posix(),sha256=digest(folder/n)) for r,n in ROLES.items()}
    outputs={f'keep/{n}{s}':digest(folder/f'keep/{n}{s}') for n in ('kernel_oracle','module_a','module_b') for s in ('.fatbin','.ptx','.cudafe1.stub.c')}
    m=dict(schema_version=1,case_id='arc.runtime_kernel',source_tree=source_fingerprint(ROOT),inputs={n:digest(ROOT/n) for n in INPUTS},
           producer=dict(path=producer.relative_to(ROOT).as_posix(),sha256=digest(producer)),artifacts=artifacts,compiler_outputs=outputs,modes=[])
    for mode in MODES:
        seed=secrets.randbelow(999990)+1
        bundle,_=prepare_bundle(folder/('control.exe' if mode=='retire' else 'host.exe'),folder/('noop.dll' if mode=='noop' else 'ct_cuda.dll'),[folder/'kernel_oracle.fatbin'] if mode=='retire' else [],folder/'runs',runtime_dll=folder/'ct_cudart.dll')
        payloads={('control.exe' if mode=='retire' else 'host.exe'):('control' if mode=='retire' else 'application'),'cudart64_12.dll':'runtime','nvcuda.dll':'noop' if mode=='noop' else 'driver'}
        if mode=='retire':payloads['kernel_oracle.fatbin']='image'
        if mode=='noop':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll');payloads['ct_underlying.dll']='driver'
        r=subprocess.run([str(bundle/('control.exe' if mode=='retire' else 'host.exe')),'single' if mode=='noop' else mode,str(seed)],cwd=bundle,capture_output=True,timeout=120)
        out=folder/(mode+'.stdout');err=folder/(mode+'.stderr');out.write_bytes(r.stdout);err.write_bytes(r.stderr)
        m['modes'].append(dict(mode=mode,seed=seed,exit_code=r.returncode,stdout=out.relative_to(ROOT).as_posix(),stderr=err.relative_to(ROOT).as_posix(),bundle=bundle.relative_to(ROOT).as_posix(),payloads=payloads))
    path=folder/'kernel-manifest.json';path.write_text(json.dumps(m,indent=2),encoding='utf-8')
    errors=audit_manifest(path,execute=True)
    if errors:raise ValueError(errors[0])
    (ROOT/'.cache/p09a2-kernel-latest.json').write_text(json.dumps(dict(manifest=path.relative_to(ROOT).as_posix())),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--producer',type=Path,required=True);a=p.parse_args()
    try:capture(a.folder,a.producer);print('Actual nvcc Runtime kernel oracle and no-op controls passed')
    except (OSError,ValueError,subprocess.SubprocessError):print('Kernel execution failed; local diagnostics retained');raise SystemExit(1)
