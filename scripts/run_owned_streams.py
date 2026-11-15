"""Real nvcc-created streams and kernel submission; diagnostic synchronous backend."""
import json
from pathlib import Path
import secrets
import shutil
import subprocess
from run_default_stream_sync import build as build_sync
from run_relaxed_nvcc import compiler_args,host_environment,command,digest,verify_files,prepare_bundle
from run_validation import source_fingerprint
ROOT=Path(__file__).resolve().parents[1]


def validate_result(value,seed):
    return (type(value) is dict and set(value)=={'status','seed','elements','streams'}
            and value['status']=='pass' and type(value['seed']) is int and value['seed']==seed
            and type(value['elements']) is int and value['elements']==32
            and type(value['streams']) is int and value['streams']==2)


def build():
    sync_path=build_sync();folder=sync_path.parent
    fingerprint=source_fingerprint(ROOT)
    if json.loads(sync_path.read_bytes())['source_fingerprint']!=fingerprint:raise ValueError('source differs')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder)
    shutil.copyfile(ROOT/'tests/fixtures/owned_streams_runtime.cu',folder/'vector.cu')
    (folder/'keep').mkdir()
    cuda=compiler_args(folder,producer.parent,base['host'])
    command(cuda,folder,env,'owned-cuda')
    cl=base['host']['tools']['cl.exe']['path']
    noop=[cl,'/nologo','/W4','/WX','/LD','/DNOOP_LAUNCH',str(ROOT/'tests/p04a_noop_driver.c'),
          '/Fe:owned-noop.dll','/link','/DEF:'+str(ROOT/'tests/p04a_driver_control.def')]
    command(noop,folder,env,'owned-noop')
    names=['default.exe','vector.cu','ct_cuda.dll','ct_cudart.dll','owned-noop.dll']
    names += [p.relative_to(folder).as_posix() for p in (folder/'keep').iterdir() if p.is_file() and p.suffix in ('.ptx','.fatbin')]
    files={n:digest(folder/n) for n in names};runs=[]
    seeds=[secrets.randbelow(1000000)+1 for _ in range(3)]
    for index,mode in enumerate(('positive','positive','noop')):
        provider=folder/('owned-noop.dll' if mode=='noop' else 'ct_cuda.dll')
        bundle,_=prepare_bundle(folder/'default.exe',provider,[],folder/'owned-runs',runtime_dll=folder/'ct_cudart.dll')
        if mode=='noop':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        result=subprocess.run([str(bundle/'default.exe'),str(seeds[index])],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.bin').write_bytes(result.stdout);(bundle/'stderr.bin').write_bytes(result.stderr)
        verify_files(bundle,pins)
        if mode=='positive':
            if result.returncode or result.stderr or not validate_result(json.loads(result.stdout),seeds[index]):
                raise ValueError('owned stream kernel failed')
        elif result.returncode!=42 or result.stdout or result.stderr:raise ValueError('no-op failed to expose bad data')
        runs.append(dict(mode=mode,seed=seeds[index],exit_code=result.returncode,bundle=bundle.relative_to(folder).as_posix(),
                         files=pins,stdout_sha256=digest(bundle/'stdout.bin'),stderr_sha256=digest(bundle/'stderr.bin')))
    verify_files(folder,files)
    if source_fingerprint(ROOT)!=fingerprint:raise ValueError('source changed')
    manifest=dict(scope='diagnostic_owned_streams',release_claim=False,source_fingerprint=fingerprint,
                  sync_manifest_sha256=digest(sync_path),commands=dict(cuda=cuda,noop=noop),files=files,runs=runs)
    path=folder/'owned-streams-manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    return path

if __name__=='__main__':
    print(json.dumps(dict(status='pass',manifest=build().relative_to(ROOT).as_posix(),release_claim=False)))
