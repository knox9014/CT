"""Standalone typed deny fixture. No CUDA Runtime table exposure."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import uuid
from check_bootstrap_tables import COMMIT,validate_inventory,verify_sources
from run_validation import source_fingerprint
from run_runtime_bootstrap import ARCHIVE_SHA,SDK
from run_relaxed_nvcc import host_environment
from run_cupy_bootstrap import digest
from prepare_spirv_tools import extract_pinned
from run_bootstrap_peer import export_names
from ct import inspect_pe

ROOT=Path(__file__).resolve().parents[1]
FIXTURE_IMPORTS={'kernel32.dll','vcruntime140.dll','api-ms-win-core-synch-l1-2-0.dll','api-ms-win-crt-runtime-l1-1-0.dll','ntdll.dll'}
RUST_TEST_IMPORTS=FIXTURE_IMPORTS|{'api-ms-win-crt-heap-l1-1-0.dll','api-ms-win-crt-locale-l1-1-0.dll',
    'api-ms-win-crt-math-l1-1-0.dll','api-ms-win-crt-stdio-l1-1-0.dll','bcryptprimitives.dll','userenv.dll'}


def inventory(exports,fixture_imports,host_imports,rust_test_imports):
    if (exports!={'ctTableGet','ctTableState'} or fixture_imports!=FIXTURE_IMPORTS
            or host_imports!={'kernel32.dll'} or rust_test_imports!=RUST_TEST_IMPORTS):
        raise ValueError('unreviewed fixture export/dependency surface')


def validate_native(value):
    expected=dict(scope='typed_deny_direct',checks=47,mask=511,stopped=True,loaded_same_file=True,
                  unloaded=True,runtime_exposed=False,application_supported=False)
    if type(value) is not dict or value!=expected or any(type(value[k]) is not type(v) for k,v in expected.items()):
        raise ValueError('native contract/role/wiring/teardown')


def surface(folder):
    fixture=inspect_pe((folder/'tables.dll').read_bytes(),dll=True,diagnostic=True)
    host=inspect_pe((folder/'native.exe').read_bytes(),diagnostic=True)
    rust=inspect_pe((folder/'rust-tests.exe').read_bytes(),diagnostic=True)
    inventory(export_names((folder/'exports.txt').read_text(errors='replace')),
              {i['library'].lower() for i in fixture['imports']},{i['library'].lower() for i in host['imports']},
              {i['library'].lower() for i in rust['imports']})


def unchanged(folder,record):
    if source_fingerprint(ROOT)!=record['source_fingerprint']:raise ValueError('source drift')
    if digest(Path(record['archive']))!=ARCHIVE_SHA:raise ValueError('SDK archive drift')
    for row in record['tools'].values():
        if digest(Path(row['path']))!=row['sha256']:raise ValueError('tool drift')
    for name,sha in record['artifacts'].items():
        file=(folder/name).resolve()
        if not file.is_relative_to(folder.resolve()) or digest(file)!=sha:raise ValueError('artifact drift/escape')
    data=json.loads((ROOT/'docs/compatibility/bootstrap-tables.json').read_bytes())
    verify_sources(data,Path(record['public_source_root']))
    surface(folder)


def audit(folder,record):
    unchanged(folder,record)
    if [r['label'] for r in record['runs']]!=['rust-tests','direct-native']:raise ValueError('run order')
    for row in record['runs']:
        if type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('native fault/contract failure')
        if row['observations']!={n:digest(folder/n) for n in (row['label']+'.stdout',row['label']+'.stderr')}:raise ValueError('observation drift')
    text=(folder/'rust-tests.stdout').read_text(encoding='utf-8')
    if 'test result: ok. 3 passed; 0 failed; 0 ignored;' not in text:raise ValueError('Rust contract count')
    validate_native(json.loads((folder/'direct-native.stdout').read_bytes()))
    return dict(status='diagnostic_pass',scope='typed_deny_fixture',rust_tests=3,native_checks=47,
                callback_bits=9,mask=511,stop_latched=True,runtime_exposed=False,application_supported=False,
                shipping_version_authorized=False)


def capture(archive,public_sources):
    data=json.loads((ROOT/'docs/compatibility/bootstrap-tables.json').read_bytes())
    validate_inventory(data);verify_sources(data,public_sources)
    folder=ROOT/'.cache/typed-table-runs'/uuid.uuid4().hex;folder.mkdir(parents=True)
    fingerprint=source_fingerprint(ROOT)
    extract_pinned(archive,ARCHIVE_SHA,folder/'sdk')
    base,env=host_environment(ROOT/'.cache/p09a2-producer/manifest.json',folder)
    compiler=Path(base['host']['tools']['cl.exe']['path']);dumpbin=compiler.parent/'dumpbin.exe'
    rustc=Path(subprocess.check_output(['rustup','which','rustc'],text=True).strip()).resolve()
    tools={name:dict(path=str(path),sha256=digest(path)) for name,path in
           [('rustc',rustc),('cl',compiler),('link',Path(base['host']['tools']['link.exe']['path'])),('dumpbin',dumpbin)]}
    commands={}
    def build(label,argv):
        if source_fingerprint(ROOT)!=fingerprint:raise ValueError('source drift during build')
        if any(digest(Path(t['path']))!=t['sha256'] for t in tools.values()):raise ValueError('tool drift during build')
        commands[label]=argv
        with (folder/(label+'.log')).open('wb') as log:subprocess.run(argv,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    build('fixture',[str(rustc),'--edition=2021','--crate-type','cdylib','-C','panic=abort','-D','warnings',str(ROOT/'tests/bootstrap_tables.rs'),'-o',str(folder/'tables.dll')])
    build('tests',[str(rustc),'--edition=2021','--test','-D','warnings',str(ROOT/'tests/bootstrap_tables_tests.rs'),'-o',str(folder/'rust-tests.exe')])
    build('host',[str(compiler),'/nologo','/utf-8','/W4','/WX','/std:c++17','/MT','/EHsc','/I'+str(folder/'sdk'/SDK/'include'),
                  str(ROOT/'tests/bootstrap_tables_native.cpp'),'/Fo:'+str(folder/'native.obj'),'/Fe:'+str(folder/'native.exe')])
    with (folder/'exports.txt').open('wb') as output:subprocess.run([str(dumpbin),'/exports',str(folder/'tables.dll')],stdout=output,check=True,timeout=30)
    surface(folder)
    files=[folder/n for n in ('tables.dll','rust-tests.exe','native.exe','native.obj','exports.txt')]
    files.extend(p for p in (folder/'sdk').rglob('*') if p.is_file())
    record=dict(source_fingerprint=fingerprint,archive=str(archive.resolve()),public_source_root=str(public_sources.resolve()),tools=tools,
                artifacts={p.relative_to(folder).as_posix():digest(p) for p in files},commands=commands,runs=[])
    for label,argv in [('rust-tests',[str(folder/'rust-tests.exe')]),('direct-native',[str(folder/'native.exe'),str(folder/'tables.dll')])]:
        unchanged(folder,record)
        clean_env={k:v for k,v in os.environ.items() if not k.upper().startswith(('CUDA','CUPY','CT_','PYTHON','NVRTC'))}
        child=subprocess.run(argv,cwd=folder,env=clean_env,capture_output=True,timeout=60)
        for suffix,raw in [('stdout',child.stdout),('stderr',child.stderr)]:(folder/(label+'.'+suffix)).write_bytes(raw)
        record['runs'].append(dict(label=label,exit_code=child.returncode,observations={n:digest(folder/n) for n in (label+'.stdout',label+'.stderr')}))
        (folder/'progress.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        if child.returncode!=0:raise ValueError('native fault/contract failure; stopped')
        if label=='rust-tests':
            if 'test result: ok. 3 passed; 0 failed; 0 ignored;' not in child.stdout.decode():raise ValueError('Rust count; stopped')
        else:validate_native(json.loads(child.stdout))
    record['summary']=audit(folder,record)
    (folder/'capture.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return folder,record['summary']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,default=ROOT/'.cache/r2b-runtime-12.9/runtime.zip')
    p.add_argument('--source-root',type=Path,default=ROOT/'.cache/r2g-public'/COMMIT);p.add_argument('--recheck',type=Path);args=p.parse_args()
    if args.recheck:
        folder=args.recheck.resolve()
        if not folder.is_relative_to((ROOT/'.cache/typed-table-runs').resolve()):raise ValueError('local fixture capture required')
        record=json.loads((folder/'capture.json').read_bytes());summary=audit(folder,record)
        if summary!=record['summary']:raise ValueError('summary drift')
        (folder/'recheck.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    else:folder,summary=capture(args.archive.resolve(),args.source_root.resolve())
    print(json.dumps(dict(run=folder.name,**summary)))
