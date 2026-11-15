"""Compile original matrixMul; inspect actual blockers without executing its kernels."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import zipfile

from run_relaxed_nvcc import command, verify_files, host_environment, compiler_args, digest, payload, ptx_tokens, source_fingerprint, audit_probe
from ct import inspect_pe
from block_barrier_check import decode
import hashlib
from run_upstream_vectoradd import audit as audit_vector

ROOT=Path(__file__).resolve().parents[1]
COMMIT='2b689228b746248b7bb7d2778d5ea0701669f7d3'
PINS={'matrixMul.cu':'ac470baa613a391e90f148c064cc60320395419995beb3b0e8ad8ba43bdfa8bb',
      'Common/helper_functions.h':'3fdcd18e41ffc2a9c88ade3595384e9cd05a2d84f80b86a2d5982035ca79c426',
      'Common/helper_image.h':'bc1fe7921bafad278ffa2e4bc8a99c18825208b9f5f47842a7cf7e86cae8b3f1',
      'Common/helper_timer.h':'c48552a7c7b7a5840fcfbc176bfb5a19b501fdc56796b64a63e78e39ab547078',
      'Common/exception.h':'ad043023a652bf3610671aad88237383c7bf2e17c66f8da5830d1d668fe7bbe7',
      'Common/helper_cuda.h':'7c514aba698325bf53a26bf8e711eeb6efd354fac45ea011486c3d907eec62c7',
      'Common/helper_string.h':'616ac8b2588a6e73aed207f85faf0da5e617404390df1790f6637b1042dbcc94'}
INPUTS=['scripts/triage_matrixmul.py','scripts/ct.py','scripts/run_relaxed_nvcc.py',
        'scripts/prepare_nvcc_default.py','scripts/prepare_nvcc_probe.py','scripts/run_validation.py',
        'scripts/check_runtime_profile.py','scripts/block_barrier_check.py','tests/test_loader_diagnostics.py','tests/test_matrixmul_triage.py']
PROFILER_PACKAGE='e8bccbfda35abc7076ba6623578d11d05966a9c7fed817cbfe7d4dea9627057e'
PROFILER_HEADER='c8973678f0c821e7a3938e0ce37fd6af49c3b4995b215b204c1959002f558322'


def profiler_archive():
    p=ROOT/'.cache/vendor/cuda_profiler_api-windows-x86_64-12.0.76-archive.zip'
    if digest(p)!=PROFILER_PACKAGE:raise ValueError('official profiler package changed')
    return p


def cuda_command(folder, producer, base):
    args=compiler_args(folder,producer.parent,base['host'])
    return ['matrixMul.cu' if x=='vector.cu' else 'matrixMul.exe' if x=='default.exe' else x for x in args]+['-I',str(folder/'Common'),'-I',str(folder/'profiler')]


def process(argv, folder, label):
    result=subprocess.run([str(x) for x in argv],cwd=ROOT,capture_output=True,timeout=90)
    (folder/(label+'.stdout')).write_bytes(result.stdout)
    (folder/(label+'.stderr')).write_bytes(result.stderr)
    return result


def observation_commands(folder,reference,out):
    return {'inspect':[sys.executable,str(ROOT/'scripts/ct.py'),'inspect','--runtime','--diagnostic',str(folder/'matrixMul.exe')],
            'strict-inspect':[sys.executable,str(ROOT/'scripts/ct.py'),'inspect','--runtime',str(folder/'matrixMul.exe')],
            'translate':[str(folder/'translate_module.exe'),str(folder/'keep/matrixMul.ptx'),str(out/'translated.spv')]}


def exact(a,b):
    if type(a) is not type(b):return False
    if isinstance(b,dict):return a.keys()==b.keys() and all(exact(a[k],v) for k,v in b.items())
    if isinstance(b,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    return a==b


def derive_diagnostic(folder,reference,observations):
    if set(observations)!={'directory','commands','returncodes'}:raise ValueError('observation schema')
    out=(folder/observations['directory']).resolve()
    if not out.is_relative_to(folder/'observations') or observations['commands']!=observation_commands(folder,reference,out):
        raise ValueError('observation command/escape')
    report=inspect_pe((folder/'matrixMul.exe').read_bytes(),runtime=True,diagnostic=True)
    missing=bool(report['unsupported_imports'])
    if type(observations['returncodes']) is not dict:raise ValueError('returncode schema')
    expected={'inspect':0,'strict-inspect':2 if missing else 0,'translate':observations['returncodes'].get('translate')}
    if type(expected['translate']) is not int or expected['translate'] not in (0,3):raise ValueError('translator exit not qualified')
    codes=observations['returncodes']
    if type(codes) is not dict or set(codes)!=set(expected) or any(type(codes[k]) is not int or codes[k]!=v for k,v in expected.items()):
        raise ValueError('observed exit codes differ')
    if report['compatibility']!=('blocked' if missing else 'unproven'):
        raise ValueError('matrixMul diagnostic classification differs')
    if (out/'inspect.stderr').read_bytes() or not exact(json.loads((out/'inspect.stdout').read_bytes()),report):
        raise ValueError('public diagnostic differs')
    strict=({'status':'error','reason':'unsupported static Runtime symbol'} if missing else inspect_pe((folder/'matrixMul.exe').read_bytes(),runtime=True))
    if (out/'strict-inspect.stderr').read_bytes() or not exact(json.loads((out/'strict-inspect.stdout').read_bytes()),strict):
        raise ValueError('strict inspection differs')
    if (out/'translate.stdout').read_bytes():raise ValueError('unexpected translator output')
    text=(folder/'keep/matrixMul.ptx').read_text(encoding='utf-8')
    common=dict(shared_declarations=len(re.findall(r'^\s*\.shared\b',text,re.M)),
                block_barriers=len(re.findall(r'\bbar\.sync\b',text)),
                fused_multiply_adds=len(re.findall(r'\bfma\.rn\.f32\b',text)))
    output=out/'translated.spv'
    if codes['translate']==0:
        if (out/'translate.stderr').read_bytes() or not output.is_file():raise ValueError('translation success without closed output')
        offline=dict(status='translated',validation='not_run',**translated_summary(output.read_bytes()),**common)
    else:
        if output.exists():raise ValueError('rejected translation produced output')
        error=re.fullmatch(rb'line=(\d+) category=(unsupported)\r?\n?',(out/'translate.stderr').read_bytes())
        lines=text.splitlines()
        if not error or not 1<=int(error[1])<=len(lines):raise ValueError('unrecognized translator rejection')
        rejected_line=lines[int(error[1])-1].strip().split()
        if not rejected_line:raise ValueError('empty rejected PTX line')
        offline=dict(status='rejected',line=int(error[1]),category=error[2].decode(),first_token=rejected_line[0],**common)
    return dict(imports=report,strict_inspect_exit=codes['strict-inspect'],application_execution_performed=False,
                gpu_execution_performed=False,offline_ptx=offline)


def translated_summary(data):
    if len(data)>16777216:raise ValueError('translated module extent')
    words,ops=decode(data)
    if words[1]!=0x10000 or words[3]==0:raise ValueError('translated module profile')
    functions={a[1] for op,a,_ in ops if op==54 and len(a)==4}
    entries={a[1] for op,a,_ in ops if op==15 and len(a)>2 and a[0]==6}
    if not entries or not entries<=functions:raise ValueError('translated entry definitions')
    sets={a[0] for op,a,_ in ops if op==11 and b''.join(v.to_bytes(4,'little') for v in a[1:]).rstrip(b'\0')==b'OpenCL.std'}
    return dict(module_sha256=hashlib.sha256(data).hexdigest(),entry_count=len(entries),
                fma_instructions=sum(op==12 and len(a)==7 and a[2] in sets and a[3]==26 for op,a,_ in ops))


def inspect_capture(folder, reference, files):
    out=folder/'observations'/uuid.uuid4().hex;out.mkdir(parents=True)
    argv=observation_commands(folder,reference,out)
    observations=dict(directory=out.relative_to(folder).as_posix(),commands=argv,returncodes={})
    for role,command in argv.items():
        verify_files(folder,files)
        observations['returncodes'][role]=process(command,out,role).returncode
        verify_files(folder,files)
    return derive_diagnostic(folder,reference,observations),observations


def validate_saved_diagnostic(folder,reference,observations,diagnostic):
    if not exact(diagnostic,derive_diagnostic(folder,reference,observations)):raise ValueError('saved diagnostic differs')


def observation_files(folder,observations):
    prefix=observations['directory']
    files={prefix+'/'+role+'.'+stream:digest(folder/prefix/(role+'.'+stream))
            for role in ('inspect','strict-inspect','translate') for stream in ('stdout','stderr')}
    if observations['returncodes']['translate']==0:files[prefix+'/translated.spv']=digest(folder/prefix/'translated.spv')
    return files


def audit(path):
    folder=path.resolve().parent
    if not folder.is_relative_to(ROOT/'.cache/matrixmul-triage'):raise ValueError('triage escape')
    m=json.loads(path.read_bytes())
    if (set(m)!={'schema_version','scope','release_claim','source_fingerprint','inputs','upstream',
                 'producer_sha256','commands','reference','files','diagnostic','observations','profiler_package_sha256'}
            or type(m['schema_version']) is not int or m['schema_version']!=3
            or m['scope']!='diagnostic_matrixmul_translation' or m['release_claim'] is not False
            or m['upstream']!={'revision':COMMIT,'tier':'upstream_adjusted_build','sources':PINS}):
        raise ValueError('triage scope/schema')
    if m['source_fingerprint']!=source_fingerprint(ROOT) or m['inputs']!={p:digest(ROOT/p) for p in INPUTS}:
        raise ValueError('triage source drift')
    producer=ROOT/'.cache/p09a2-producer/manifest.json'
    if m['profiler_package_sha256']!=PROFILER_PACKAGE or digest(profiler_archive())!=PROFILER_PACKAGE:
        raise ValueError('profiler provenance differs')
    if digest(producer)!=m['producer_sha256'] or audit_probe(producer):raise ValueError('triage producer drift')
    base=json.loads(producer.read_bytes())
    if base['host']['profile']!='diagnostic' or m['commands']!=commands(folder,producer,base):
        raise ValueError('triage recipe drift')
    required=set(PINS)|{'matrixMul.exe','translate_module.exe','profiler/cuda_profiler_api.h','keep/matrixMul.ptx','keep/matrixMul.fatbin',
                        'keep/matrixMul_dlink.fatbin','keep/matrixMul.cudafe1.stub.c','keep/matrixMul_dlink.reg.c'}
    if not required<=set(m['files']):raise ValueError('triage artifact missing')
    verify_files(folder,m['files'])
    if any(m['files'][n]!=sha for n,sha in PINS.items()):raise ValueError('upstream source changed')
    if m['files']['profiler/cuda_profiler_api.h']!=PROFILER_HEADER:raise ValueError('profiler header changed')
    exe=(folder/'matrixMul.exe').read_bytes()
    if any((folder/'keep'/n).read_bytes() not in exe for n in ('matrixMul.fatbin','matrixMul_dlink.fatbin')):
        raise ValueError('matrixMul images absent from EXE')
    if ptx_tokens(payload(folder/'keep/matrixMul.fatbin'))!=ptx_tokens((folder/'keep/matrixMul.ptx').read_bytes()):
        raise ValueError('matrixMul payload differs')
    ref=m['reference'];directory=(ROOT/ref['path']).resolve()
    if not directory.is_relative_to(ROOT/'.cache/upstream-vectoradd-runs') or set(ref['files'])!={'ct_cuda.dll','ct_cudart.dll'}:
        raise ValueError('reference escape/schema')
    verify_files(directory,ref['files'])
    vector=audit_vector(directory/'manifest.json')
    if ref['files']!={n:vector['files'][n] for n in ('ct_cuda.dll','ct_cudart.dll')}:raise ValueError('reference DLL identity differs')
    validate_saved_diagnostic(folder,directory,m['observations'],m['diagnostic'])
    if any(m['files'].get(n)!=sha for n,sha in observation_files(folder,m['observations']).items()):
        raise ValueError('observation hashes absent or changed')
    return m,directory


def commands(folder,producer,base):
    return dict(cuda=cuda_command(folder,producer,base),
                translator=['cargo','build','--locked','-p','ct-codegen-spirv','--example','translate_module',
                            '--target-dir',str(ROOT/'.cache/matrixmul-triage-target')])


def build():
    folder=ROOT/'.cache/matrixmul-triage'/uuid.uuid4().hex;folder.mkdir(parents=True)
    source=ROOT/'.cache/upstream-sources'/COMMIT;verify_files(source,PINS)
    for name in PINS:
        dst=folder/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,dst)
    with zipfile.ZipFile(profiler_archive()) as z:
        names=[n for n in z.namelist() if n.endswith('/include/cuda_profiler_api.h')]
        if len(names)!=1:raise ValueError('profiler package member set')
        (folder/'profiler').mkdir();(folder/'profiler/cuda_profiler_api.h').write_bytes(z.read(names[0]))
    if digest(folder/'profiler/cuda_profiler_api.h')!=PROFILER_HEADER:raise ValueError('profiler header hash')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder)
    if base['host']['profile']!='diagnostic':raise ValueError('diagnostic recipe only')
    fingerprint=source_fingerprint(ROOT);inputs={p:digest(ROOT/p) for p in INPUTS}
    argv=commands(folder,producer,base);(folder/'keep').mkdir()
    command(argv['cuda'],folder,env,'cuda')
    command(argv['translator'],folder,dict(os.environ,CARGO_INCREMENTAL='0'),'translator',cwd=ROOT)
    shutil.copyfile(ROOT/'.cache/matrixmul-triage-target/debug/examples/translate_module.exe',folder/'translate_module.exe')
    ref_path=ROOT/json.loads((ROOT/'.cache/upstream-vectoradd-latest.json').read_bytes())['manifest']
    reference=ref_path.resolve().parent;ref=audit_vector(ref_path)
    if not reference.is_relative_to(ROOT/'.cache/upstream-vectoradd-runs'):raise ValueError('reference path escape')
    pins={name:ref['files'][name] for name in ('ct_cuda.dll','ct_cudart.dll')};verify_files(reference,pins)
    names=list(PINS)+['matrixMul.exe','translate_module.exe','profiler/cuda_profiler_api.h']+[p.relative_to(folder).as_posix() for p in (folder/'keep').iterdir()
            if p.is_file() and (p.suffix in ('.ptx','.fatbin') or p.name.endswith(('.stub.c','.reg.c','.fatbin.c')))]
    files={n:digest(folder/n) for n in names};diagnostic,observations=inspect_capture(folder,reference,files);verify_files(folder,files)
    files.update(observation_files(folder,observations))
    m=dict(schema_version=3,scope='diagnostic_matrixmul_translation',release_claim=False,source_fingerprint=fingerprint,
           inputs=inputs,upstream={'revision':COMMIT,'tier':'upstream_adjusted_build','sources':PINS},
           producer_sha256=digest(producer),commands=argv,reference={'path':reference.relative_to(ROOT).as_posix(),'files':pins},
           files=files,diagnostic=diagnostic,observations=observations,profiler_package_sha256=PROFILER_PACKAGE)
    path=folder/'manifest.json';path.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8');audit(path)
    return path,m


def recheck(path):
    path=path.resolve()
    m,reference=audit(path);sha=digest(path)
    diagnostic,observations=inspect_capture(path.parent,reference,m['files'])
    if diagnostic!=m['diagnostic']:raise ValueError('repeated diagnostic differs')
    verify_files(path.parent,m['files']);verify_files(reference,m['reference']['files'])
    if sha!=digest(path) or m['source_fingerprint']!=source_fingerprint(ROOT):raise ValueError('recheck input drift')
    report=dict(manifest_sha256=sha,diagnostic=diagnostic,observations=observations,
                files=observation_files(path.parent,observations))
    (path.parent/('recheck-'+uuid.uuid4().hex+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return m


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--recheck',type=Path);args=parser.parse_args()
    try:
        path=args.recheck
        if path:m=recheck(path)
        else:path,m=build()
        print(json.dumps(dict(status='inspected',application_status='unproven' if not m['diagnostic']['imports']['unsupported_imports'] and m['diagnostic']['offline_ptx']['status']=='translated' else 'blocked',application_execution_performed=False,
                              gpu_execution_performed=False,manifest=path.resolve().relative_to(ROOT).as_posix(),
                              diagnostic=m['diagnostic'])))
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        print(json.dumps(dict(status='fail',reason='matrixmul_triage_failed')));raise SystemExit(1)
