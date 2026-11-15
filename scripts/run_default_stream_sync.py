"""Local null-stream Runtime ABI checks; no independent streams/async claim."""
import json
from pathlib import Path
import shutil
import subprocess
from run_runtime_attribute import build as build_attribute, CORE, ROOT
from run_relaxed_nvcc import host_environment, command, digest, verify_files
from run_validation import source_fingerprint


def validate_result(mode, value):
    if type(value) is not dict or value.get('status') != 'pass':
        return False
    if mode == 'positive':
        return (set(value) == {'status','checked_bytes','context_preserved'}
                and type(value['checked_bytes']) is int and value['checked_bytes'] == 1028
                and value['context_preserved'] is True)
    if mode == 'sync_error':
        return (set(value) == {'status','error','context_preserved'}
                and type(value['error']) is int and value['error'] == 709
                and value['context_preserved'] is True)
    return (mode == 'absent' and set(value) == {'status','error'}
            and type(value['error']) is int and value['error'] == 35)


def build():
    attribute_path = build_attribute()
    folder = attribute_path.parent
    source = source_fingerprint(ROOT)
    attribute = json.loads(attribute_path.read_bytes())
    if source != attribute['source_fingerprint']:
        raise ValueError('attribute source differs')
    producer = ROOT / '.cache/p09a2-producer/manifest.json'
    base, env = host_environment(producer, folder)
    cl = base['host']['tools']['cl.exe']['path']
    commands = {}
    def run(label, argv):
        commands[label] = argv
        command(argv, folder, env, label)
    run('stream-consumer',[cl,'/nologo','/utf-8','/W4','/WX','/EHsc','/std:c++17',
         '/I'+str(producer.parent/'toolkit/include'),
         str(ROOT/'tests/runtime_stream_native_abi.cpp'),'/Fe:stream.exe'])
    definition = folder/'sync-error.def'
    definition.write_text('EXPORTS\n'+'\n'.join(CORE+['cuCtxCreate_v2','cuCtxDestroy_v2'])+'\n')
    run('sync-error',[cl,'/nologo','/utf-8','/W4','/WX','/LD',
         str(ROOT/'tests/runtime_sync_error_driver.c'),'/Fe:sync-error.dll',
         '/link','/DEF:'+str(definition)])
    files = {name:digest(folder/name) for name in ['stream.exe','ct_cuda.dll','ct_cudart.dll','sync-error.dll']}
    runs=[]
    for mode in ('positive','sync_error','absent'):
        bundle=folder/('stream-'+mode);bundle.mkdir()
        shutil.copyfile(folder/'stream.exe',bundle/'stream.exe')
        shutil.copyfile(folder/'ct_cudart.dll',bundle/'cudart64_12.dll')
        if mode!='absent':
            shutil.copyfile(folder/('sync-error.dll' if mode=='sync_error' else 'ct_cuda.dll'),bundle/'nvcuda.dll')
        if mode=='sync_error':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        result=subprocess.run([str(bundle/'stream.exe'),str(bundle/'cudart64_12.dll'),mode],
                              cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(result.stdout);(bundle/'stderr.txt').write_bytes(result.stderr)
        verify_files(bundle,pins)
        if result.returncode or result.stderr:raise ValueError('stream native failed: '+mode)
        value=json.loads(result.stdout)
        if not validate_result(mode,value):raise ValueError('stream result failed')
        runs.append(dict(mode=mode,exit_code=result.returncode,result=value,files=pins,
                         stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    verify_files(folder,files)
    if source_fingerprint(ROOT)!=source:raise ValueError('source changed')
    manifest=dict(scope='diagnostic_default_stream_sync',release_claim=False,source_fingerprint=source,
                  attribute_manifest_sha256=digest(attribute_path),commands=commands,files=files,runs=runs)
    path=folder/'stream-manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    return path

if __name__=='__main__':
    print(json.dumps(dict(status='pass',manifest=build().relative_to(ROOT).as_posix(),release_claim=False)))
