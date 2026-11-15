"""Driver-only GPU event5 capture; Runtime event APIs remain unimplemented."""
import json
import math
from pathlib import Path
import secrets
import shutil
import subprocess

from run_queued_copy import build as build_queued
from run_runtime_attribute import ROOT
from run_relaxed_nvcc import host_environment, command, digest, verify_files
from run_validation import source_fingerprint
from check_compatibility_profile import expected_exports


def validate_result(value, seed):
    return (type(value) is dict and set(value)=={'status','seed','milliseconds','roundtrips','words','ownership','capacity'}
            and value['status']=='pass' and type(value['seed']) is int and value['seed']==seed
            and type(value['milliseconds']) in (int,float) and math.isfinite(value['milliseconds'])
            and 0<value['milliseconds']<60000 and type(value['roundtrips']) is int and value['roundtrips']==8
            and type(value['words']) is int and value['words']==1024 and value['ownership'] is True
            and type(value['capacity']) is int and value['capacity']==128)


def validate_control(mode, code, stdout, stderr):
    expected={'record_noop':b'EVENT_TIMING_REJECT code=400 milliseconds=987.5\n',
              'zero_time':b'EVENT_TIMING_REJECT code=0 milliseconds=0\n'}
    return mode in expected and code==42 and stdout==b'' and stderr.replace(b'\r\n',b'\n')==expected[mode]


def build():
    queued=build_queued();folder=queued.parent;fingerprint=source_fingerprint(ROOT)
    if json.loads(queued.read_bytes())['source_fingerprint']!=fingerprint:raise ValueError('source differs')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder)
    cl=base['host']['tools']['cl.exe']['path'];commands={}
    def run(label,args):commands[label]=args;command(args,folder,env,label)
    run('event-consumer',[cl,'/nologo','/utf-8','/W4','/WX','/EHsc','/std:c++17',
        '/I'+str(producer.parent/'toolkit/include'),str(ROOT/'tests/driver_event_native_abi.cpp'),'/Fe:driver-event.exe'])
    definition=folder/'events.def';definition.write_text('EXPORTS\n'+'\n'.join(expected_exports(ROOT))+'\n')
    for mode,macro in [('record_noop','EVENT_NOOP_RECORD'),('zero_time','EVENT_ZERO_TIME')]:
        run(mode,[cl,'/nologo','/utf-8','/W4','/WX','/LD','/D'+macro,
            str(ROOT/'tests/host_memory_driver_proxy.c'),'/Fe:event-'+mode+'.dll','/link','/DEF:'+str(definition)])
    files={n:digest(folder/n) for n in ['ct_cuda.dll','ct_cudart.dll','driver-event.exe','event-record_noop.dll','event-zero_time.dll']}
    runs=[]
    for mode in ('positive','positive','record_noop','zero_time'):
        seed=secrets.randbelow(1000000)+1
        bundle=folder/('event-'+mode+'-'+str(seed));bundle.mkdir()
        shutil.copyfile(folder/'driver-event.exe',bundle/'driver-event.exe')
        shutil.copyfile(folder/('ct_cuda.dll' if mode=='positive' else 'event-'+mode+'.dll'),bundle/'nvcuda.dll')
        if mode!='positive':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        result=subprocess.run([str(bundle/'driver-event.exe'),str(bundle/'nvcuda.dll'),str(seed)],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr);verify_files(bundle,pins)
        observed=None
        if mode=='positive':
            observed=json.loads(result.stdout)
            if result.returncode or result.stderr or not validate_result(observed,seed):raise ValueError('Driver event native check failed')
        elif not validate_control(mode,result.returncode,result.stdout,result.stderr):raise ValueError('event omission control failed')
        runs.append(dict(mode=mode,seed=seed,exit_code=result.returncode,result=observed,bundle=bundle.relative_to(folder).as_posix(),files=pins,
                         stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    verify_files(folder,files)
    if source_fingerprint(ROOT)!=fingerprint:raise ValueError('source changed')
    target=folder/'driver-events-manifest.json'
    target.write_text(json.dumps(dict(scope='diagnostic_driver_events',release_claim=False,source_fingerprint=fingerprint,
        queued_manifest_sha256=digest(queued),files=files,commands=commands,runs=runs),indent=2)+'\n')
    (ROOT/'.cache/driver-events-latest.json').write_text(json.dumps(dict(manifest=target.relative_to(ROOT).as_posix()))+'\n')
    return target


if __name__=='__main__':
    print(json.dumps(dict(status='pass',manifest=build().relative_to(ROOT).as_posix(),release_claim=False)))
