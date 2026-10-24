"""Bind real kernel ABI probes, typed calls and provider controls to artifacts."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from prepare_nvcc_probe import audit_probe, digest
from run_validation import source_fingerprint

ROOT=Path(__file__).resolve().parents[1]
EXPECTED=b'DEFAULT_ABI 1 8\n'
ROLES={'runtime':'ct_cudart.dll','reference':'runtime_default_reference_abi.exe',
       'declared':'runtime_default_declared_abi.exe','native':'runtime_default_native_abi.exe',
       'missing':'missing.dll','forwarded':'forwarded.dll','foreign':'ct_foreign.dll'}
INPUTS=['include/ct_cudart.h','tests/runtime_default_reference_abi.cpp',
        'tests/runtime_default_declared_abi.cpp','tests/runtime_default_native_abi.cpp',
        'tests/p09a2_missing_kernel_driver.c','tests/p09a2_foreign_kernel_driver.c',
        'tests/p09a2_forwarded_kernel.def','scripts/check_runtime_default_abi.ps1',
        'scripts/runtime_default_abi_evidence.py']
MODES=('pure','missing','forwarded')


def check_output(mode,code,out):
    expected=('DEFAULT_NATIVE '+mode+(' 16\n' if mode=='pure' else ' 19\n')).encode('ascii')
    return [] if mode in MODES and code==0 and out.replace(b'\r\n',b'\n')==expected else ['kernel ABI native mismatch']


def local(root,name):
    p=(root/name).resolve()
    if not p.is_relative_to(root/'.cache/p09a2c-build'):raise ValueError('artifact escape')
    return p


def audit(path,root=ROOT,*,execute=False):
    try:
        value=json.loads(Path(path).read_bytes())
        if set(value)!={'case_id','source_tree','inputs','producer','artifacts','observations'} or value['case_id']!='arc.runtime_default_abi':return ['ABI schema mismatch']
        if value['source_tree']!=source_fingerprint(root):return ['ABI source mismatch']
        if value['inputs']!={n:digest(root/n) for n in INPUTS}:return ['ABI inputs changed']
        producer=value['producer']
        if set(producer)!={'path','sha256'} or digest(root/producer['path'])!=producer['sha256']:return ['ABI producer changed']
        producer_path=(root/producer['path']).resolve()
        if not producer_path.is_relative_to(root/'.cache') or audit_probe(producer_path):return ['ABI producer invalid']
        if set(value['artifacts'])!=set(ROLES):return ['ABI artifacts absent']
        for role,item in value['artifacts'].items():
            if set(item)!={'path','sha256'}:return ['ABI artifact schema']
            p=local(root,item['path'])
            if p.name!=ROLES[role] or digest(p)!=item['sha256']:return ['ABI artifact changed']
        if set(value['observations'])!={'reference','declared',*MODES}:return ['ABI probes absent']
        folder=local(root,value['artifacts']['native']['path']).parent
        for mode,item in value['observations'].items():
            if set(item)!={'stdout','sha256','exit_code','payloads'}:return ['ABI observation schema']
            output=local(root,item['stdout'])
            if digest(output)!=item['sha256']:return ['ABI output changed']
            out=output.read_bytes()
            expected_payloads={} if mode in ('reference','declared') else {'host.exe':'native','cudart64_12.dll':'runtime'}
            if mode!='pure' and mode in MODES:expected_payloads['nvcuda.dll']=mode
            if mode=='forwarded':expected_payloads['ct_foreign.dll']='foreign'
            if item['payloads']!=expected_payloads:return ['ABI bundle mismatch']
            bundle=folder/mode
            for name,role in expected_payloads.items():
                if digest(bundle/name)!=value['artifacts'][role]['sha256']:return ['ABI bundle changed']
            if mode in ('reference','declared'):
                if item['exit_code'] or out.replace(b'\r\n',b'\n')!=EXPECTED:return ['ABI declaration mismatch']
                command=[str(local(root,value['artifacts'][mode]['path']))]
            else:
                if check_output(mode,item['exit_code'],out):return ['ABI typed native mismatch']
                command=[str(bundle/'host.exe'),str(bundle/'cudart64_12.dll'),mode]
            if execute:
                run=subprocess.run(command,cwd=bundle if mode in MODES else folder,capture_output=True,timeout=30)
                if run.returncode!=item['exit_code'] or run.stdout.replace(b'\r\n',b'\n')!=out.replace(b'\r\n',b'\n'):return ['ABI independent replay failed']
        if execute:return audit(path,root,execute=False)
        return []
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):return ['kernel ABI evidence unavailable']


def capture(folder,producer):
    folder=folder.resolve();producer=producer.resolve()
    if not folder.is_relative_to(ROOT/'.cache/p09a2c-build') or audit_probe(producer):raise ValueError('unverified ABI inputs')
    artifacts={role:dict(path=(folder/name).relative_to(ROOT).as_posix(),sha256=digest(folder/name)) for role,name in ROLES.items()}
    value=dict(case_id='arc.runtime_default_abi',source_tree=source_fingerprint(ROOT),inputs={n:digest(ROOT/n) for n in INPUTS},
               producer=dict(path=producer.relative_to(ROOT).as_posix(),sha256=digest(producer)),artifacts=artifacts,observations={})
    for mode in ('reference','declared',*MODES):
        bundle=folder/mode;bundle.mkdir(exist_ok=True)
        payloads={} if mode in ('reference','declared') else {'host.exe':'native','cudart64_12.dll':'runtime'}
        if mode!='pure' and mode in MODES:payloads['nvcuda.dll']=mode
        if mode=='forwarded':payloads['ct_foreign.dll']='foreign'
        for name,role in payloads.items():shutil.copyfile(ROOT/artifacts[role]['path'],bundle/name)
        command=[str(folder/ROLES[mode])] if mode in ('reference','declared') else [str(bundle/'host.exe'),str(bundle/'cudart64_12.dll'),mode]
        run=subprocess.run(command,cwd=bundle,capture_output=True,timeout=30)
        out=folder/(mode+'.stdout');out.write_bytes(run.stdout);(folder/(mode+'.stderr')).write_bytes(run.stderr)
        value['observations'][mode]=dict(stdout=out.relative_to(ROOT).as_posix(),sha256=digest(out),exit_code=run.returncode,payloads=payloads)
    manifest=folder/'default-abi-manifest.json';manifest.write_text(json.dumps(value,indent=2),encoding='utf-8')
    if audit(manifest,execute=True):raise ValueError('kernel ABI capture failed; local artifacts retained')
    (ROOT/'.cache/p09a2c-abi-latest.json').write_text(json.dumps(dict(manifest=manifest.relative_to(ROOT).as_posix())),encoding='utf-8')


def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--producer',type=Path,required=True);a=p.parse_args()
    try:capture(a.folder,a.producer);print('Kernel ABI declarations and typed native controls passed');return 0
    except (OSError,ValueError,subprocess.SubprocessError):print('Kernel ABI failed; local diagnostics retained');return 1
if __name__=='__main__':raise SystemExit(main())
