"""Runtime event generations, owned extension controls and genuine nvcc work."""
import json
import math
import secrets
import shutil
import subprocess
from run_driver_events import build as build_driver
from run_runtime_attribute import CORE,ROOT
from run_relaxed_nvcc import command,host_environment,digest,verify_files,compiler_args,prepare_bundle
from run_queued_copy import validate_kernel
from run_validation import source_fingerprint

EVENTS=['cuEventCreate','cuEventRecord','cuEventSynchronize','cuEventDestroy_v2','cuEventElapsedTime']

def validate_native(mode,value):
    if mode!='positive':
        fields={'status','error'} if mode=='absent' else {'status','error','core_alive','extension_verified'}
        return (mode in ['absent','forwarded']+['missing_'+str(i) for i in range(5)] and type(value) is dict and set(value)==fields and value['status']=='pass'
                and type(value['error']) is int and value['error']==35 and (mode=='absent' or value['core_alive'] is True and value['extension_verified'] is True))
    return (type(value) is dict and set(value)=={'status','milliseconds','context_preserved'} and value['status']=='pass'
            and type(value['milliseconds']) in (int,float) and math.isfinite(value['milliseconds']) and value['milliseconds']>0
            and value['context_preserved'] is True)

def build():
    driver=build_driver();folder=driver.parent;fingerprint=source_fingerprint(ROOT)
    if json.loads(driver.read_bytes())['source_fingerprint']!=fingerprint:raise ValueError('source differs')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder);cl=base['host']['tools']['cl.exe']['path'];commands={}
    def run(label,args):commands[label]=args;command(args,folder,env,label)
    include=str(producer.parent/'toolkit/include')
    for role in ('reference','declared'):
        label='event-runtime-'+role
        run(label,[cl,'/nologo','/utf-8','/W4','/WX','/EHsc','/std:c++17','/I'+include,str(ROOT/('tests/runtime_'+role+'_abi.cpp')),'/Fe:'+label+'.exe'])
        result=subprocess.run([str(folder/(label+'.exe'))],cwd=folder,capture_output=True,timeout=30)
        if result.returncode or result.stderr:raise ValueError('Runtime event signature mismatch')
        (folder/(label+'.stdout')).write_bytes(result.stdout)
    if (folder/'event-runtime-reference.stdout').read_bytes()!=(folder/'event-runtime-declared.stdout').read_bytes():raise ValueError('Runtime ABI differs')
    run('event-native',[cl,'/nologo','/utf-8','/W4','/WX','/EHsc','/std:c++17','/I'+include,str(ROOT/'tests/runtime_event_native_abi.cpp'),'/Fe:runtime-event.exe'])
    foreign=folder/'event_foreign.c';foreign.write_text('__declspec(dllexport) int __stdcall event_foreign(void){return 999;}\n')
    run('event-foreign',[cl,'/nologo','/W4','/WX','/LD',str(foreign),'/Fe:event_foreign.dll'])
    modes=['positive','absent']
    for index,name in enumerate(EVENTS):
        mode='missing_'+str(index);modes.append(mode)
        definition=folder/(mode+'.def');definition.write_text('EXPORTS\n'+'\n'.join(CORE+[s for s in EVENTS if s!=name])+'\n')
        run('event-'+mode,[cl,'/nologo','/utf-8','/W4','/WX','/LD',str(ROOT/'tests/host_memory_driver_proxy.c'),'/Fe:event-'+mode+'.dll','/link','/DEF:'+str(definition)])
    modes.append('forwarded');definition=folder/'event-forwarded.def'
    definition.write_text('EXPORTS\n'+'\n'.join(CORE+EVENTS[1:]+['cuEventCreate=event_foreign.event_foreign'])+'\n')
    run('event-forwarded',[cl,'/nologo','/utf-8','/W4','/WX','/LD','/DcuEventCreate=ct_hidden_create',str(ROOT/'tests/host_memory_driver_proxy.c'),str(folder/'event_foreign.lib'),'/Fe:event-forwarded.dll','/link','/DEF:'+str(definition)])
    files={name:digest(folder/name) for name in ['ct_cuda.dll','ct_cudart.dll','runtime-event.exe','event-runtime-reference.exe','event-runtime-declared.exe','event-runtime-reference.stdout','event-runtime-declared.stdout','event_foreign.dll']+['event-'+m+'.dll' for m in modes if m not in ('positive','absent')]}
    controls=[]
    for mode in modes:
        bundle=folder/('runtime-event-'+mode);bundle.mkdir();shutil.copyfile(folder/'runtime-event.exe',bundle/'runtime-event.exe');shutil.copyfile(folder/'ct_cudart.dll',bundle/'cudart64_12.dll')
        if mode!='absent':shutil.copyfile(folder/('ct_cuda.dll' if mode=='positive' else 'event-'+mode+'.dll'),bundle/'nvcuda.dll')
        if mode not in ('absent','positive'):shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        if mode=='forwarded':shutil.copyfile(folder/'event_foreign.dll',bundle/'event_foreign.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        result=subprocess.run([str(bundle/'runtime-event.exe'),str(bundle/'cudart64_12.dll'),mode],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr);verify_files(bundle,pins)
        if result.returncode or result.stderr or not validate_native(mode,json.loads(result.stdout)):raise ValueError('Runtime event native/control failed: '+mode)
        controls.append(dict(mode=mode,result=json.loads(result.stdout),files=pins,bundle=bundle.relative_to(folder).as_posix(),stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    shutil.copyfile(ROOT/'tests/fixtures/event_queue_runtime.cu',folder/'events.cu');(folder/'keep-events').mkdir()
    args=[('events.cu' if x=='vector.cu' else 'events.exe' if x=='default.exe' else 'keep-events' if x=='keep' else x) for x in compiler_args(folder,producer.parent,base['host'])]
    run('events-cuda',args)
    files.update({name:digest(folder/name) for name in ['events.cu','events.exe']})
    runs=[]
    for mode in ('positive','positive','noop_launch','noop_copy','noop_record','zero_time'):
        seed=secrets.randbelow(1000000)+1
        provider={'positive':'ct_cuda.dll','noop_launch':'host-noop.dll','noop_copy':'copy-noop.dll','noop_record':'event-record_noop.dll','zero_time':'event-zero_time.dll'}[mode]
        bundle,_=prepare_bundle(folder/'events.exe',folder/provider,[],folder/'event-queue-runs',runtime_dll=folder/'ct_cudart.dll')
        if mode!='positive':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        result=subprocess.run([str(bundle/'events.exe'),str(seed)],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr);verify_files(bundle,pins)
        if mode=='positive':
            if result.returncode or result.stderr or not validate_kernel(json.loads(result.stdout),seed):raise ValueError('event queue numerical test failed')
        elif mode=='noop_record':
            line=next(i for i,s in enumerate((ROOT/'tests/fixtures/event_queue_runtime.cu').read_text().splitlines(),1) if 'CHECK(cudaEventElapsedTime(' in s)
            expected=('queued CUDA error 400 line '+str(line)+'\n').encode()
            if result.returncode!=41 or result.stdout or result.stderr.replace(b'\r\n',b'\n')!=expected:raise ValueError('record omission failed')
        elif mode=='zero_time':
            if result.returncode!=43 or result.stdout or result.stderr:raise ValueError('zero event time control failed')
        elif result.returncode!=42 or result.stdout or result.stderr:raise ValueError('copy/launch omission control failed')
        runs.append(dict(mode=mode,seed=seed,exit_code=result.returncode,files=pins,bundle=bundle.relative_to(folder).as_posix(),stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    verify_files(folder,files)
    verify_files(folder,json.loads(driver.read_bytes())['files'])
    if source_fingerprint(ROOT)!=fingerprint:raise ValueError('source changed')
    target=folder/'runtime-events-manifest.json';target.write_text(json.dumps(dict(scope='diagnostic_runtime_events',release_claim=False,source_fingerprint=fingerprint,driver_manifest_sha256=digest(driver),files=files,commands=commands,controls=controls,runs=runs),indent=2)+'\n')
    (ROOT/'.cache/runtime-events-latest.json').write_text(json.dumps(dict(manifest=target.relative_to(ROOT).as_posix()))+'\n')
    return target

if __name__=='__main__':print(json.dumps(dict(status='pass',manifest=build().relative_to(ROOT).as_posix(),release_claim=False)))
