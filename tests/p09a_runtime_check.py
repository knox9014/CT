"""Execute unchanged CT-owned Runtime consumers and audit their actual payloads."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from ct import inspect_pe,prepare_bundle
from run_validation import source_fingerprint

MODES={'shared_primary':(8770,5),'ordinary_context':(8770,5),'threads':(0,4),
       'pure_no_driver':(5,1),'missing_driver':(0,2),'wrong_driver':(0,2),
       'missing_export':(0,2),'stale_reset':(0,3),'retain_probe':(0,4),
       'noop_copy':None,'noop_fill':None}
def digest(data):return hashlib.sha256(data).hexdigest()
def local(root,name):
    p=(root/name).resolve()
    if not p.is_relative_to(root/'.cache/p09a-build'):raise ValueError('artifact escape')
    return p

def audit_manifest(path,root=ROOT):
    try:
        m=json.loads(Path(path).read_text())
        if set(m)!={'schema_version','case_id','source_tree','artifacts','modes'} or m['schema_version']!=1 or m['case_id']!='arc.runtime':return ['invalid manifest']
        if m['source_tree']!=source_fingerprint(root):return ['source mismatch']
        roles={'application','driver','runtime','fake','noop_copy','noop_fill','underlying'}
        if set(m['artifacts'])!=roles:return ['artifact roles mismatch']
        for role,item in m['artifacts'].items():
            if set(item)!={'path','sha256'} or digest(local(root,item['path']).read_bytes())!=item['sha256']:return ['artifact mismatch']
        imports=inspect_pe(local(root,m['artifacts']['application']['path']).read_bytes(),runtime=True)['imports']
        from check_runtime_profile import SIGNATURES
        observed=[i for i in imports if i['library'].lower()=='cudart64_12.dll']
        if len(observed)!=1 or set(observed[0]['symbols'])!=set(SIGNATURES):return ['Runtime imports mismatch']
        if len(m['modes'])!=11 or {x['mode'] for x in m['modes']}!=set(MODES):return ['missing modes']
        for record in m['modes']:
            if set(record)!={'mode','seed','exit_code','bundle','stdout','stderr','payloads'}:return ['invalid observation']
            mode=record['mode']; seed=record['seed']
            if type(seed)is not int or not 1<=seed<=1000000:return ['invalid seed']
            directory=local(root,record['bundle'])
            for name,role in record['payloads'].items():
                if Path(name).name!=name or role not in roles:return ['invalid payload']
                if digest((directory/name).read_bytes())!=m['artifacts'][role]['sha256']:return ['changed payload']
            expected_payloads={'host.exe':'application','cudart64_12.dll':'runtime'}
            if mode not in ('pure_no_driver','missing_driver'):
                expected_payloads['nvcuda.dll']='fake' if mode=='missing_export' else mode if mode in ('noop_copy','noop_fill') else 'driver'
            if mode in ('noop_copy','noop_fill'):expected_payloads['ct_underlying.dll']='underlying'
            if record['payloads']!=expected_payloads:return ['incomplete payloads']
            stdout=local(root,record['stdout']).read_bytes(); stderr=local(root,record['stderr']).read_bytes()
            if MODES[mode] is None:
                marker=b'oracle mismatch: copy' if mode=='noop_copy' else b'oracle mismatch: fill'
                if record['exit_code']!=42 or marker not in stderr:return ['negative control not detected']
            else:
                n,o=MODES[mode]
                if record['exit_code']!=0 or json.loads(stdout)!=dict(mode=mode,status='pass',checked_bytes=n,observations=o,seed=seed):return ['native observation mismatch']
        return []
    except (OSError,ValueError,TypeError,KeyError):return ['native manifest unavailable or malformed']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('artifacts',type=Path);args=p.parse_args()
    ctypes.windll.kernel32.SetErrorMode(0x8007)
    folder=local(ROOT,str(args.artifacts)); app=folder/'host.exe';driver=ROOT/'target/debug/ct_cuda.dll';runtime=folder/'runtime-target/debug/ct_cudart.dll'
    paths={'application':app,'driver':folder/'nominal.dll','runtime':folder/'runtime.dll','fake':folder/'fake.dll','noop_copy':folder/'noop_copy.dll','noop_fill':folder/'noop_fill.dll','underlying':folder/'underlying.dll'}
    paths['driver'].write_bytes(driver.read_bytes());paths['runtime'].write_bytes(runtime.read_bytes());paths['underlying'].write_bytes(driver.read_bytes())
    manifest=dict(schema_version=1,case_id='arc.runtime',source_tree=source_fingerprint(ROOT),artifacts={role:dict(path=path.relative_to(ROOT).as_posix(),sha256=digest(path.read_bytes())) for role,path in paths.items()},modes=[])
    for mode in MODES:
        bundle,_=prepare_bundle(app,paths['driver'],[],folder/'runs',runtime_dll=paths['runtime'])
        payloads={'host.exe':'application','cudart64_12.dll':'runtime','nvcuda.dll':'driver'}
        if mode in ('pure_no_driver','missing_driver'):(bundle/'nvcuda.dll').unlink();payloads.pop('nvcuda.dll')
        if mode=='missing_export':(bundle/'nvcuda.dll').write_bytes(paths['fake'].read_bytes());payloads['nvcuda.dll']='fake'
        if mode in ('noop_copy','noop_fill'):
            (bundle/'nvcuda.dll').write_bytes(paths[mode].read_bytes());payloads['nvcuda.dll']=mode
            (bundle/'ct_underlying.dll').write_bytes(paths['underlying'].read_bytes());payloads['ct_underlying.dll']='underlying'
        seed=secrets.randbelow(1000000)+1
        arguments=[str(bundle/'host.exe'),mode,str(seed)]
        if mode=='wrong_driver':
            wrong=folder/'wrong';wrong.mkdir(exist_ok=True);(wrong/'nvcuda.dll').write_bytes(paths['fake'].read_bytes());arguments.append(str(wrong/'nvcuda.dll'))
        r=subprocess.run(arguments,cwd=bundle,capture_output=True,timeout=90)
        out=folder/(mode+'.stdout');err=folder/(mode+'.stderr');out.write_bytes(r.stdout);err.write_bytes(r.stderr)
        manifest['modes'].append(dict(mode=mode,seed=seed,exit_code=r.returncode,bundle=bundle.relative_to(ROOT).as_posix(),stdout=out.relative_to(ROOT).as_posix(),stderr=err.relative_to(ROOT).as_posix(),payloads=payloads))
        print(mode+': '+str(r.returncode),flush=True)
    path=folder/'native-manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    errors=audit_manifest(path)
    if errors:raise AssertionError(errors)
    (ROOT/'.cache/p09a-native-latest.json').write_text(json.dumps({'manifest':path.relative_to(ROOT).as_posix()}))
    print(json.dumps(dict(case_id='arc.runtime',status='pass',modes=11,positive=9,negative_controls=2)))

if __name__=='__main__':main()
