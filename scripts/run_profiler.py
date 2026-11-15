"""No-collector profiler compatibility; never claims actual profiling capture."""
import json
import secrets
import shutil
import subprocess
import zipfile
from run_runtime_events import build as build_events
from run_runtime_attribute import ROOT
from run_relaxed_nvcc import command,host_environment,compiler_args,prepare_bundle,digest,verify_files
from run_queued_copy import validate_kernel
from run_validation import source_fingerprint
from triage_matrixmul import profiler_archive,PROFILER_HEADER
from check_compatibility_profile import expected_exports

def validate_native(mode,value):
    fields={'status','mode','error'} if mode=='absent' else {'status','mode','error','context_preserved','control_verified'}
    return (mode in ('absent','positive','trap_sync','queued_error') and type(value) is dict and set(value)==fields
            and value['status']=='pass' and value['mode']==mode and type(value['error']) is int
            and value['error']==(35 if mode=='absent' else 0 if mode=='positive' else 1)
            and (mode=='absent' or value['context_preserved'] is True and value['control_verified'] is True))

def build():
    events=build_events();folder=events.parent;fp=source_fingerprint(ROOT)
    if json.loads(events.read_bytes())['source_fingerprint']!=fp:raise ValueError('source differs')
    header=folder/'profiler/cuda_profiler_api.h';header.parent.mkdir()
    with zipfile.ZipFile(profiler_archive()) as archive:
        names=[n for n in archive.namelist() if n.endswith('/include/cuda_profiler_api.h')]
        if len(names)!=1:raise ValueError('profiler archive header differs')
        header.write_bytes(archive.read(names[0]))
    if digest(header)!=PROFILER_HEADER:raise ValueError('profiler header differs')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder);cl=base['host']['tools']['cl.exe']['path'];commands={}
    def run(label,args):commands[label]=args;command(args,folder,env,label)
    include=['/external:W0','/external:I'+str(producer.parent/'toolkit/include'),'/external:I'+str(header.parent)]
    for role in ('reference','declared','native'):
        label='profiler-'+role
        run(label,[cl,'/nologo','/utf-8','/W4','/WX','/EHsc','/std:c++17',*include,str(ROOT/('tests/runtime_profiler_'+role+'_abi.cpp')),'/Fe:'+label+'.exe'])
    for role in ('reference','declared'):
        r=subprocess.run([str(folder/('profiler-'+role+'.exe'))],cwd=folder,capture_output=True,timeout=30)
        if r.returncode or r.stderr or r.stdout.replace(b'\r\n',b'\n')!=b'PROFILER_ABI 2 4 8\n':raise ValueError('profiler typed ABI failed')
        (folder/('profiler-'+role+'.stdout')).write_bytes(r.stdout)
    definition=folder/'profiler-trap.def';definition.write_text('EXPORTS\n'+'\n'.join(expected_exports(ROOT))+'\n')
    run('profiler-trap',[cl,'/nologo','/utf-8','/W4','/WX','/LD','/DCT_PROFILER_TRAP_SYNC',str(ROOT/'tests/host_memory_driver_proxy.c'),'/Fe:profiler-trap.dll','/link','/DEF:'+str(definition)])
    files={n:digest(folder/n) for n in ['ct_cuda.dll','ct_cudart.dll','profiler-reference.exe','profiler-declared.exe','profiler-native.exe','profiler-reference.stdout','profiler-declared.stdout','profiler-trap.dll','profiler/cuda_profiler_api.h']}
    controls=[]
    for mode in ('positive','absent','trap_sync','queued_error'):
        bundle=folder/('profiler-'+mode);bundle.mkdir();shutil.copyfile(folder/'profiler-native.exe',bundle/'app.exe');shutil.copyfile(folder/'ct_cudart.dll',bundle/'cudart64_12.dll')
        if mode!='absent':shutil.copyfile(folder/('profiler-trap.dll' if mode=='trap_sync' else 'ct_cuda.dll'),bundle/'nvcuda.dll')
        if mode=='trap_sync':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        r=subprocess.run([str(bundle/'app.exe'),str(bundle/'cudart64_12.dll'),mode],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(r.stdout);(bundle/'stderr.txt').write_bytes(r.stderr);verify_files(bundle,pins)
        if r.returncode or r.stderr or not validate_native(mode,json.loads(r.stdout)):raise ValueError('profiler native control failed: '+mode)
        controls.append(dict(mode=mode,result=json.loads(r.stdout),files=pins,bundle=bundle.relative_to(folder).as_posix(),stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    shutil.copyfile(ROOT/'tests/fixtures/profiler_queue_runtime.cu',folder/'profiler-queue.cu');(folder/'keep-profiler').mkdir()
    args=[('profiler-queue.cu' if a=='vector.cu' else 'profiler-queue.exe' if a=='default.exe' else 'keep-profiler' if a=='keep' else a) for a in compiler_args(folder,producer.parent,base['host'])]+['-I',str(header.parent)]
    run('profiler-cuda',args);files.update({n:digest(folder/n) for n in ['profiler-queue.cu','profiler-queue.exe']})
    runs=[]
    for mode in ('positive','positive','noop_launch','noop_copy'):
        seed=secrets.randbelow(1000000)+1;provider={'positive':'ct_cuda.dll','noop_launch':'host-noop.dll','noop_copy':'copy-noop.dll'}[mode]
        bundle,_=prepare_bundle(folder/'profiler-queue.exe',folder/provider,[],folder/'profiler-queue-runs',runtime_dll=folder/'ct_cudart.dll')
        if mode!='positive':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        r=subprocess.run([str(bundle/'profiler-queue.exe'),str(seed)],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(r.stdout);(bundle/'stderr.txt').write_bytes(r.stderr);verify_files(bundle,pins)
        if mode=='positive':
            if r.returncode or r.stderr or not validate_kernel(json.loads(r.stdout),seed):raise ValueError('profiler scope numerical test failed')
        elif r.returncode!=42 or r.stdout or r.stderr:raise ValueError('profiler scope omission control failed')
        runs.append(dict(mode=mode,seed=seed,exit_code=r.returncode,files=pins,bundle=bundle.relative_to(folder).as_posix(),stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    verify_files(folder,files);verify_files(folder,json.loads(events.read_bytes())['files'])
    if source_fingerprint(ROOT)!=fp:raise ValueError('source changed')
    target=folder/'profiler-manifest.json';target.write_text(json.dumps(dict(scope='diagnostic_no_collector_profiler',release_claim=False,source_fingerprint=fp,runtime_events_manifest_sha256=digest(events),files=files,commands=commands,controls=controls,runs=runs),indent=2)+'\n')
    (ROOT/'.cache/profiler-latest.json').write_text(json.dumps(dict(manifest=target.relative_to(ROOT).as_posix()))+'\n');return target

if __name__=='__main__':print(json.dumps(dict(status='pass',manifest=build().relative_to(ROOT).as_posix(),release_claim=False)))
