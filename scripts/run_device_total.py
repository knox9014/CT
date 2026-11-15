"""Fresh original-header ABI/native total query and forwarding-provider smoke."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid
from run_real_bootstrap import ROOT
from run_cupy_bootstrap import digest
from run_validation import source_fingerprint
from run_relaxed_nvcc import host_environment
from run_bootstrap_peer import export_names
from check_compatibility_profile import expected_exports
from check_toolchain_files import observed_platform
from compatibility_registry import validate_toolchain,validate_tool_execution
from device_total_check import validate


def headers(directory):
    lock=json.loads((ROOT/'docs/compatibility/toolchain-lock-v1.json').read_bytes())
    if validate_toolchain(lock):raise ValueError('toolchain lock')
    tool=next(t for t in lock['tools'] if t['id']=='cuda-headers')
    observed={n:digest(directory/n) for n in tool['files']}
    if validate_tool_execution(tool,observed_platform=observed_platform(),observed_hashes=observed,required=True):raise ValueError('CUDA header identity')
    return observed


def unchanged(folder,record):
    if source_fingerprint(ROOT)!=record['source_fingerprint'] or headers(Path(record['header_directory']))!=record['headers']:raise ValueError('source/header drift')
    for row in record['tools'].values():
        if digest(Path(row['path']))!=row['sha256']:raise ValueError('tool drift')
    for name,sha in record['files'].items():
        p=(folder/name).resolve()
        if not p.is_relative_to(folder.resolve()) or digest(p)!=sha:raise ValueError('artifact drift')


def audit(folder,record):
    unchanged(folder,record)
    names=set(expected_exports(ROOT))
    if len(names)!=47:raise ValueError('current Driver scope changed')
    for n in ('exports.txt','proxy-exports.txt'):
        if export_names((folder/n).read_text(encoding='utf-8'))!=names:raise ValueError('actual export inventory')
    reference=(folder/'reference.stdout').read_bytes().replace(b'\r\n',b'\n');declared=(folder/'declared.stdout').read_bytes().replace(b'\r\n',b'\n')
    if reference!=declared or sum(line.startswith(b'cu') for line in reference.splitlines())!=47:raise ValueError('original/declared ABI differs')
    if (folder/'proxy.def').read_text()!='EXPORTS\n'+'\n'.join(sorted(names))+'\n':raise ValueError('forwarding provider export definition')
    if [r['mode'] for r in record['runs']]!=['nominal','forwarded']:raise ValueError('native role order')
    results=[]
    for row in record['runs']:
        bundle=folder/row['mode']
        if type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('native child failure')
        if row['observations']!={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}:raise ValueError('native observation drift')
        value=json.loads((bundle/'stdout.json').read_bytes());results.append(validate(value,forwarded=row['mode']=='forwarded'))
        provider='ct_cuda.dll' if row['mode']=='nominal' else 'proxy.dll'
        expected=record['files']['target/debug/ct_cuda.dll'] if row['mode']=='nominal' else record['files']['proxy.dll']
        if digest(bundle/provider)!=expected:raise ValueError('copied provider differs')
        if row['mode']=='forwarded' and digest(bundle/'ct_underlying.dll')!=record['files']['target/debug/ct_cuda.dll']:raise ValueError('underlying provider differs')
    if results[0]!=results[1]:raise ValueError('forwarded total/device differs')
    return dict(status='native_pass',driver_exports=47,abi_signatures=47,native_children=2,total_bytes=results[0]['total_bytes'],device_name=results[0]['device_name'],
                legacy_output_abi_rejected=True,tls_preserved=True,application_supported=False,shipping_version_authorized=False)


def capture(header_directory):
    fingerprint=source_fingerprint(ROOT);observed=headers(header_directory)
    folder=ROOT/'.cache/device-total-runs'/uuid.uuid4().hex;folder.mkdir(parents=True)
    host,env=host_environment(ROOT/'.cache/p09a2-producer/manifest.json',folder)
    compiler=Path(host['host']['tools']['cl.exe']['path']);dumpbin=compiler.parent/'dumpbin.exe'
    rustc=Path(subprocess.check_output(['rustup','which','rustc'],text=True).strip());cargo=Path(shutil.which('cargo'))
    paths=dict(cl=compiler,link=Path(host['host']['tools']['link.exe']['path']),dumpbin=dumpbin,rustc=rustc,cargo=cargo)
    tools={n:dict(path=str(p),sha256=digest(p)) for n,p in paths.items()};commands={}
    def run(label,argv,environment=env):
        if source_fingerprint(ROOT)!=fingerprint or headers(header_directory)!=observed or any(digest(Path(t['path']))!=t['sha256'] for t in tools.values()):raise ValueError('build input drift')
        commands[label]=argv
        with (folder/(label+'.log')).open('wb') as log:subprocess.run(argv,cwd=folder,env=environment,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    run('driver',[str(cargo),'build','--locked','--manifest-path',str(ROOT/'Cargo.toml'),'-p','ct-cuda','--target-dir',str(folder/'target')],dict(os.environ,CARGO_INCREMENTAL='0'))
    for role,source in (('reference','cuda_reference_abi.cpp'),('declared','cuda_declared_abi.cpp'),('consumer','device_total_native_abi.cpp')):
        run(role,[str(compiler),'/nologo','/utf-8','/W4','/WX','/EHsc','/std:c++17','/I'+str(header_directory),str(ROOT/'tests'/source),'/Fo:'+str(folder/(role+'.obj')),'/Fe:'+str(folder/(role+'.exe'))])
    names=set(expected_exports(ROOT));(folder/'proxy.def').write_text('EXPORTS\n'+'\n'.join(sorted(names))+'\n',encoding='utf-8')
    run('proxy',[str(compiler),'/nologo','/utf-8','/W4','/WX','/LD',str(ROOT/'tests/host_memory_driver_proxy.c'),'/Fo:'+str(folder/'proxy.obj'),'/Fe:'+str(folder/'proxy.dll'),'/link','/DEF:'+str(folder/'proxy.def')])
    for name,binary in [('exports.txt',folder/'target/debug/ct_cuda.dll'),('proxy-exports.txt',folder/'proxy.dll')]:
        with (folder/name).open('wb') as log:subprocess.run([str(dumpbin),'/exports',str(binary)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
    for role in ('reference','declared'):
        child=subprocess.run([str(folder/(role+'.exe'))],cwd=folder,capture_output=True,timeout=30)
        if child.returncode or child.stderr:raise ValueError('ABI probe failed')
        (folder/(role+'.stdout')).write_bytes(child.stdout)
    files=[p for p in folder.iterdir() if p.is_file()]+[folder/'target/debug/ct_cuda.dll']
    record=dict(source_fingerprint=fingerprint,header_directory=str(header_directory),headers=observed,tools=tools,commands=commands,
                files={p.relative_to(folder).as_posix():digest(p) for p in files},runs=[])
    for mode in ('nominal','forwarded'):
        unchanged(folder,record);bundle=folder/mode;bundle.mkdir()
        provider='ct_cuda.dll' if mode=='nominal' else 'proxy.dll'
        shutil.copyfile(folder/'target/debug/ct_cuda.dll' if mode=='nominal' else folder/'proxy.dll',bundle/provider)
        expected=record['files']['target/debug/ct_cuda.dll'] if mode=='nominal' else record['files']['proxy.dll']
        if digest(bundle/provider)!=expected:raise ValueError('copied provider drift')
        if mode=='forwarded':
            shutil.copyfile(folder/'target/debug/ct_cuda.dll',bundle/'ct_underlying.dll')
            if digest(bundle/'ct_underlying.dll')!=record['files']['target/debug/ct_cuda.dll']:raise ValueError('underlying provider drift')
        argv=[str(folder/'consumer.exe'),str(bundle/provider)]+(['forwarded'] if mode=='forwarded' else [])
        clean={k:v for k,v in os.environ.items() if not k.upper().startswith(('CUDA','CUPY','CT_','PYTHON','NVRTC'))}
        child=subprocess.run(argv,cwd=bundle,env=clean,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(child.stdout);(bundle/'stderr.txt').write_bytes(child.stderr)
        record['runs'].append(dict(mode=mode,exit_code=child.returncode,observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}))
        (folder/'progress.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        if child.returncode!=0:raise ValueError('device-total native failure; stopped')
        validate(json.loads(child.stdout),forwarded=mode=='forwarded')
    record['summary']=audit(folder,record);(folder/'capture.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return folder,record['summary']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--header-directory',type=Path,default=ROOT/'.cache/reference/cuda-12.0/include');p.add_argument('--recheck',type=Path);args=p.parse_args()
    if args.recheck:
        folder=args.recheck.resolve()
        if not folder.is_relative_to((ROOT/'.cache/device-total-runs').resolve()):raise ValueError('local capture required')
        record=json.loads((folder/'capture.json').read_bytes());summary=audit(folder,record)
        if summary!=record['summary']:raise ValueError('summary drift')
        (folder/'recheck.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    else:folder,summary=capture(args.header_directory.resolve())
    print(json.dumps(dict(run=folder.name,**summary)))
