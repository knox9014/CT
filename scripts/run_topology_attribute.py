"""Guarded CT metadata ABI + independent native maximum-topology control."""
import argparse
import ctypes as c
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from cache_budget import ensure_budget,GIB
from run_runtime_attribute import validate_result
from run_relaxed_nvcc import command,host_environment,digest,verify_files
from run_validation import source_fingerprint
from virtual_target_check import ABI_MODES,abi_valid
from topology_attribute_check import TOPOLOGY_MODES,topology_valid

ROOT=Path(__file__).resolve().parents[1]
POLICY_MODES=tuple(ABI_MODES)+('loader_missing','loader_forwarded','loader_absent')
HEADER_SHA='3e7967d37ce79a472205c9cc230da837173ba390686bc4017e980e1290e40feb'


def environment():
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('CUDA','CUPY','CT_','PYTHON','NVRTC','ZE_','ZES_'))}
    env['CARGO_INCREMENTAL']='0'
    return env


def parent_capture():
    child=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/run_runtime_attribute.py')],cwd=ROOT,env=environment(),capture_output=True,timeout=300)
    if child.returncode:raise ValueError('parent attribute qualification failed')
    row=json.loads(child.stdout)
    if row.get('status')!='pass' or type(row.get('manifest')) is not str:raise ValueError('parent scope')
    path=(ROOT/row['manifest']).resolve()
    if not path.is_relative_to((ROOT/'.cache/runtime-attribute-runs').resolve()):raise ValueError('parent path')
    return path


def route_for(kind,mode):
    if kind=='baseline':return mode
    if kind=='policy':return mode.removeprefix('loader_') if mode.startswith('loader_') else 'normal'
    return 'minimal' if mode.startswith('minimal_') else mode if mode in ('missing','forwarded','absent') else 'normal'


def payloads(files,kind,mode):
    route=route_for(kind,mode)
    consumer='attribute.exe' if kind=='baseline' else 'topology.exe' if kind=='topology' else 'virtual-policy.exe'
    wanted={consumer if kind=='baseline' else 'consumer.exe':files[consumer],'cudart64_12.dll':files['ct_cudart.dll']}
    if route!='absent':wanted['nvcuda.dll']=files['ct_cuda.dll' if route=='normal' else route+'.dll']
    if route in ('minimal','missing','forwarded'):wanted['ct_underlying.dll']=files['ct_cuda.dll']
    if route=='forwarded':wanted['foreign.dll']=files['foreign.dll']
    return wanted


def bundle_files(bundle,wanted):
    if bundle.is_symlink() or bundle.is_junction() or not bundle.is_dir():raise ValueError('linked/missing bundle')
    if {p.name for p in bundle.iterdir()}!=set(wanted)|{'stdout.json','stderr.txt'}:raise ValueError('bundle membership')
    if any(p.is_symlink() or p.is_junction() or not p.is_file() for p in bundle.iterdir()):raise ValueError('linked/nonregular bundle file')
    verify_files(bundle,wanted)


def validate_row(folder,files,row,kind,mode):
    if type(row) is not dict or set(row)!={'mode','files','exit_code','observations'} or row['mode']!=mode:raise ValueError('child role/schema')
    if type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('child failure')
    bundle=folder/kind/mode
    if bundle.resolve().parent!=(folder/kind).resolve() or (folder/kind).is_symlink() or (folder/kind).is_junction():raise ValueError('child directory')
    wanted=payloads(files,kind,mode)
    if row['files']!=wanted:raise ValueError('child payload identity')
    bundle_files(bundle,wanted)
    if row['observations']!={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')} or (bundle/'stderr.txt').read_bytes():raise ValueError('child observations')
    value=json.loads((bundle/'stdout.json').read_bytes())
    valid=topology_valid(mode,value) if kind=='topology' else abi_valid('loader' if mode.startswith('loader_') else mode,value)
    if not valid:raise ValueError('independent ABI oracle')
    return value


def validate_parent_identity(path,parent,record):
    if (parent.get('scope')!='diagnostic_runtime_attribute' or parent.get('release_claim') is not False
            or parent.get('source_fingerprint')!=record['source_fingerprint']
            or digest(path)!=record['parent_manifest_sha256']):raise ValueError('parent role/source/hash')


def audit(folder,record):
    folder=folder.resolve()
    if not folder.is_relative_to((ROOT/'.cache/runtime-attribute-runs').resolve()):raise ValueError('local topology run required')
    if record.get('scope')!='ct_maximum_topology_abi' or record.get('release_claim') is not False or record.get('source_fingerprint')!=source_fingerprint(ROOT):raise ValueError('topology source/scope')
    parent_path=folder/'manifest.json';parent=json.loads(parent_path.read_bytes())
    validate_parent_identity(parent_path,parent,record)
    if record['files']!={**parent['files'],**{n:digest(folder/n) for n in ('topology.exe','virtual-policy.exe','ze_api.h')}}:raise ValueError('topology file set')
    verify_files(folder,record['files'])
    if record['files']['ze_api.h']!=HEADER_SHA:raise ValueError('official Level Zero header')
    if set(record['tools'])!={'cl','link','ze_loader'}:raise ValueError('required native tools')
    for tool in record['tools'].values():
        if digest(Path(tool['path']))!=tool['sha256']:raise ValueError('tool identity drift')
    if digest(Path(record['producer']['path']))!=record['producer']['sha256'] or record['producer']['sha256']!=parent['producer_sha256']:raise ValueError('producer identity')
    if [r['mode'] for r in parent['runs']]!=['normal','minimal','missing','forwarded','absent']:raise ValueError('baseline modes')
    for row in parent['runs']:
        mode=row['mode'];bundle=folder/mode;wanted=payloads(parent['files'],'baseline',mode)
        if type(row['exit_code']) is not int or row['exit_code']!=0 or row['files']!=wanted:raise ValueError('baseline role')
        bundle_files(bundle,wanted)
        value=json.loads((bundle/'stdout.json').read_bytes())
        if (value!=row['result'] or not validate_result(mode,value) or (bundle/'stderr.txt').read_bytes()
                or digest(bundle/'stdout.json')!=row['stdout_sha256'] or digest(bundle/'stderr.txt')!=row['stderr_sha256']):raise ValueError('baseline outcome')
    values=[]
    for kind,modes in (('topology',TOPOLOGY_MODES),('policy',POLICY_MODES)):
        rows=record[kind+'_runs']
        if [r['mode'] for r in rows]!=list(modes):raise ValueError('ABI mode order')
        for row,mode in zip(rows,modes):
            value=validate_row(folder,record['files'],row,kind,mode)
            if kind=='topology' and mode not in ('missing','forwarded','absent'):values.append(value)
    controls=[(v['device_name'],v['max_slices'],v['max_subslices_per_slice'],v['topology_count']) for v in values]
    if any(v!=controls[0] for v in controls):raise ValueError('physical topology changed between processes')
    return dict(status='diagnostic_pass',native_processes=25,baseline_processes=5,topology_processes=9,policy_processes=11,
                device_name=controls[0][0],max_slices=controls[0][1],max_subslices_per_slice=controls[0][2],topology_count=controls[0][3],
                strict16_code=801,maxima_only=True,application_supported=False,nvidia_sm_claim=False,release_claim=False)


def build():
    ensure_budget(ROOT,GIB)
    fingerprint=source_fingerprint(ROOT);parent_path=parent_capture();folder=parent_path.parent
    producer=ROOT/'.cache/p09a2-producer/manifest.json';host,env=host_environment(producer,folder)
    compiler=Path(host['host']['tools']['cl.exe']['path'])
    header=ROOT/'.cache/reference/ze_api.h'
    if digest(header)!=HEADER_SHA:raise ValueError('unqualified Level Zero header')
    shutil.copyfile(header,folder/'ze_api.h')
    commands={}
    for label,source in (('topology','topology_native_abi.cpp'),('virtual-policy','virtual_target_native_abi.cpp')):
        argv=[str(compiler),'/nologo','/utf-8','/W4','/WX','/EHsc','/std:c++17','/I'+str(folder),
              '/I'+str(producer.parent/'toolkit/include'),str(ROOT/'tests'/source),'/Fo:'+str(folder/(label+'.obj')),'/Fe:'+str(folder/(label+'.exe'))]
        commands[label]=argv;command(argv,folder,env,label,cwd=folder)
    files={**json.loads(parent_path.read_bytes())['files'],**{n:digest(folder/n) for n in ('topology.exe','virtual-policy.exe','ze_api.h')}}
    kernel=c.WinDLL('kernel32');system=c.create_unicode_buffer(32768)
    kernel.GetSystemDirectoryW.argtypes=[c.c_wchar_p,c.c_uint];kernel.GetSystemDirectoryW.restype=c.c_uint
    length=kernel.GetSystemDirectoryW(system,len(system))
    if not 0<length<len(system):raise ValueError('system loader path')
    loader=Path(system.value)/'ze_loader.dll'
    record=dict(scope='ct_maximum_topology_abi',release_claim=False,source_fingerprint=fingerprint,parent_manifest_sha256=digest(parent_path),
                files=files,tools={n:dict(path=str(p),sha256=digest(p)) for n,p in (('cl',compiler),('link',Path(host['host']['tools']['link.exe']['path'])),('ze_loader',loader))},
                producer=dict(path=str(producer),sha256=digest(producer)),commands=commands,topology_runs=[],policy_runs=[])
    for kind,modes in (('topology',TOPOLOGY_MODES),('policy',POLICY_MODES)):
        for mode in modes:
            if source_fingerprint(ROOT)!=fingerprint:raise ValueError('source changed before native child')
            bundle=folder/kind/mode;bundle.mkdir(parents=True)
            wanted=payloads(files,kind,mode)
            for target,sha in wanted.items():
                source=next((folder/n for n,h in files.items() if h==sha),None)
                if source is None:raise ValueError('missing payload source')
                shutil.copyfile(source,bundle/target)
            actual_mode='loader' if kind=='policy' and mode.startswith('loader_') else mode
            argv=[str(bundle/'consumer.exe'),str(bundle/'cudart64_12.dll'),str(bundle/'nvcuda.dll'),actual_mode]
            child=subprocess.run(argv,cwd=bundle,env=environment(),capture_output=True,timeout=90)
            (bundle/'stdout.json').write_bytes(child.stdout);(bundle/'stderr.txt').write_bytes(child.stderr)
            row=dict(mode=mode,files=wanted,exit_code=child.returncode,observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')})
            record[kind+'_runs'].append(row);(folder/'topology-progress.json').write_text(json.dumps(record,indent=2))
            validate_row(folder,files,row,kind,mode)
    record['summary']=audit(folder,record)
    path=folder/'topology-manifest.json';path.write_text(json.dumps(record,indent=2));return path


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--recheck',type=Path);args=parser.parse_args()
    path=args.recheck.resolve() if args.recheck else build()
    record=json.loads(path.read_bytes());summary=audit(path.parent,record)
    if summary!=record['summary']:raise ValueError('saved topology summary drift')
    (path.parent/'topology-recheck.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(dict(run=path.parent.name,**summary)))
