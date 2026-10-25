"""Build bounded P04a CUDA globals and reconstruct native execution evidence."""
import argparse, json, os, secrets, shutil, subprocess, sys, uuid
from pathlib import Path
from prepare_nvcc_default import host_environment
from prepare_nvcc_probe import digest
from ct import prepare_bundle, inspect_pe
from run_validation import source_fingerprint
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from p04a_runtime_check import validate
from p04a_driver_check import observe

SOURCES=['tests/fixtures/p04a/global_runtime.cu','tests/fixtures/p09a2/default_unsupported_global.cu',
 'tests/p04a_runtime_check.py','tests/p04a_driver_check.py','scripts/run_p04a_smoke.py',
 'tests/p04a_noop_driver.c','tests/p09a_noop_driver.c','tests/p04a_driver_control.def',
 'tests/p09a_driver_control.def','tests/p04a_forwarded_global.def','tests/p04a_foreign_global.c',
 'tests/p04a_extension_control.cpp','include/ct_cuda.h','include/ct_cudart.h','scripts/p04a_evidence.py','scripts/global_negative.py']

CASES=[('global_runtime','host',True),('default_unsupported_global','negative',True)]

def run(argv, folder, env, name):
    completed=subprocess.run([str(x) for x in argv],cwd=folder,env=env,capture_output=True,timeout=180)
    (folder/(name+'.stdout')).write_bytes(completed.stdout)
    (folder/(name+'.stderr')).write_bytes(completed.stderr)
    if completed.returncode:raise ValueError('build command failed: '+name)

def compiler_commands(producer,folder,base,root=ROOT):
    commands=[]
    toolkit=producer.resolve().parent
    compiler=Path(base['host']['tools']['cl.exe']['path']); nvcc=toolkit/'toolkit/bin/nvcc.exe'
    common=[str(nvcc),'--std=c++17','--compiler-bindir',str(compiler.parent),'-allow-unsupported-compiler','-I',str(toolkit/'stl'),'-Xcompiler','/utf-8','--cudart=shared','--keep','--generate-code','arch=compute_52,code=compute_52']
    for stem,exe,device_runtime in CASES:
        keep=folder/('keep-'+stem)
        args=common+['--keep-dir',keep.name]
        if not device_runtime:args+=['--cudadevrt=none']
        commands.append(dict(name=exe,argv=args+[stem+'.cu','-o',exe+'.exe']))
    # Build provider controls against the same CT declarations as the Driver.
    for name,source,definition,extra in [
        ('noop','p04a_noop_driver.c','p04a_driver_control.def',['/DNOOP_LAUNCH']),
        ('missing','p09a_noop_driver.c','p09a_driver_control.def',[]),
        ('ct_foreign','p04a_foreign_global.c',None,[]),
        ('forwarded','p09a_noop_driver.c','p04a_forwarded_global.def',[])]:
        args=[str(compiler),'/nologo','/W4','/WX','/LD']+extra+[str(root/'tests'/source),'/Fo'+str(folder/(name+'.obj')),'/Fe'+str(folder/(name+'.dll'))]
        if name=='forwarded':args += [str(folder/'ct_foreign.lib')]
        if definition:args+=['/link','/DEF:'+str(root/'tests'/definition)]
        commands.append(dict(name=name,argv=args))
    commands.append(dict(name='control',argv=[str(compiler),'/nologo','/W4','/WX','/EHsc','/std:c++17',str(root/'tests/p04a_extension_control.cpp'),'/Fo'+str(folder/'control.obj'),'/Fe'+str(folder/'control.exe')]))
    return commands


def rust_commands(folder):
    return [dict(name='driver-target',argv=['cargo','build','--locked','-p','ct-cuda'],output='ct_cuda.dll'),
            dict(name='runtime-target',argv=['cargo','build','--locked','--manifest-path','crates/ct-cudart/Cargo.toml'],output='ct_cudart.dll')]


def build(producer,folder):
    folder.mkdir(parents=True,exist_ok=False)
    base,env=host_environment(producer,folder)
    for source in SOURCES[:2]:shutil.copyfile(ROOT/source,folder/Path(source).name)
    for stem,_,_ in CASES:(folder/('keep-'+stem)).mkdir()
    commands=compiler_commands(producer,folder,base)
    for command in commands:run(command['argv'],folder,env,command['name'])
    build_env=os.environ.copy();build_env['CARGO_INCREMENTAL']='0'
    for command in rust_commands(folder):
        target,output=command['name'],command['output']
        build_env['CARGO_TARGET_DIR']=str(folder/target)
        r=subprocess.run(command['argv'],cwd=ROOT,env=build_env,capture_output=True,timeout=120)
        (folder/(target+'.log')).write_bytes(r.stdout+r.stderr)
        if r.returncode:raise ValueError('Rust build failed')
        shutil.copyfile(folder/target/'debug'/output,folder/output)
    return commands

def capture(folder,producer,commands):
    def item(p):return dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p))
    m=dict(schema_version=1,scope='diagnostic_p04a_globals',release_claim=False,source_tree=source_fingerprint(ROOT),
        inputs={n:digest(ROOT/n) for n in SOURCES},producer=item(producer.resolve()),commands=commands,rust_commands=rust_commands(folder),
        artifacts={n:item(folder/n) for n in ['host.exe','negative.exe','control.exe','ct_cuda.dll','ct_cudart.dll','noop.dll','missing.dll','ct_foreign.dll','forwarded.dll']},
        compiler_outputs={str(p.relative_to(folder)).replace('\\','/'):digest(p) for p in folder.glob('keep-*/*') if p.suffix in ('.ptx','.fatbin') or p.name.endswith('.cudafe1.stub.c')},runs=[])
    source_ptx=(folder/'keep-global_runtime/global_runtime.ptx').read_text()
    stub=(folder/'keep-global_runtime/global_runtime.cudafe1.stub.c').read_text()
    if not all(n in source_ptx for n in ('ct_counter','ct_zero','ct_unused','ld.volatile.global','st.volatile.global')) or '__cudaRegisterVar' not in stub:raise ValueError('compiler global metadata absent')
    imports=inspect_pe((folder/'host.exe').read_bytes(),runtime=True)['imports']
    if not any('__cudaRegisterVar' in i['symbols'] for i in imports):raise ValueError('variable import absent')
    for mode in ['positive','positive_fresh','noop','missing','forwarded','old_missing','old_forwarded','unsupported']:
        seed=secrets.randbelow(999990)+1
        application=folder/('control.exe' if mode in ('missing','forwarded') else 'negative.exe' if mode=='unsupported' else 'host.exe')
        if mode.startswith('old_'):application=producer.resolve().parent/'compressed.exe'
        provider=folder/('noop.dll' if mode=='noop' else mode.removeprefix('old_')+'.dll' if mode in ('missing','forwarded','old_missing','old_forwarded') else 'ct_cuda.dll')
        assets=[folder/'keep-global_runtime/global_runtime.fatbin'] if mode in ('missing','forwarded') else []
        bundle,_=prepare_bundle(application,provider,assets,folder/'runs',runtime_dll=folder/'ct_cudart.dll')
        if mode not in ('positive','positive_fresh','unsupported'):shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        if mode in ('forwarded','old_forwarded'):shutil.copyfile(folder/'ct_foreign.dll',bundle/'ct_foreign.dll')
        args=['used_global',str(seed)] if mode=='unsupported' else [] if mode.startswith('old_') or mode in ('missing','forwarded') else [str(seed)]
        r=subprocess.run([str(bundle/application.name)]+args,cwd=bundle,capture_output=True,timeout=120)
        out=folder/(mode+'.stdout');err=folder/(mode+'.stderr');out.write_bytes(r.stdout);err.write_bytes(r.stderr)
        if r.returncode or r.stderr:raise ValueError('native mode failed: '+mode)
        if mode.startswith('old_'):
            if r.stdout.strip()!=b'vector results correct':raise ValueError('old paths failed')
        else:
            value=json.loads(r.stdout)
            if mode in ('positive','positive_fresh') and validate(value,seed):raise ValueError('numerical global mismatch')
            if mode=='noop':
                errors=validate(value,seed)
                if errors!=['global numerical/guard/input/sequence mismatch'] or value['errors']!=[0]*200:raise ValueError('no-op not numerical negative')
                initial=[((seed*3+i*11)^0x13579bdf)&0xffffffff for i in range(145)]
                if value['runs']!=[initial]*100:raise ValueError('no-op output shape')
            if mode in ('missing','forwarded') and value!={'error':35,'memory_roundtrip':1}:raise ValueError('optional extension control failed')
            if mode=='unsupported' and value!={'seed':seed,'mode':'used_global','errors':[801],'runs':[],'main_entered':1}:raise ValueError('unsupported control failed')
        m['runs'].append(dict(mode=mode,seed=seed,exit_code=r.returncode,stdout=item(out),stderr=item(err),bundle=bundle.relative_to(ROOT).as_posix(),payloads={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}))
    # Isolate Driver stress in a child so each test has explicit native teardown.
    r=subprocess.run([sys.executable,str(ROOT/'tests/p04a_driver_check.py'),'--dll',str(folder/'ct_cuda.dll')],cwd=ROOT,capture_output=True,timeout=180)
    if r.returncode:raise ValueError('direct Driver check failed')
    out=folder/'driver.stdout';err=folder/'driver.stderr';out.write_bytes(r.stdout);err.write_bytes(r.stderr)
    m['direct_driver']=dict(exit_code=r.returncode,stdout=item(out),stderr=item(err))
    (folder/'diagnostic-manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
    return m

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--producer',type=Path,default=ROOT/'.cache/p09a2-producer/manifest.json');a=p.parse_args()
    (ROOT/'.cache/p04a-runtime-latest.json').unlink(missing_ok=True)
    folder=ROOT/'.cache/p04a-smoke'/uuid.uuid4().hex
    try:
        commands=build(a.producer.resolve(),folder);m=capture(folder,a.producer,commands)
        from p04a_evidence import audit_manifest
        if audit_manifest(folder/'diagnostic-manifest.json',ROOT,execute=True):raise ValueError('independent reconstruction failed')
        (ROOT/'.cache/p04a-runtime-latest.json').write_text(json.dumps(dict(manifest=(folder/'diagnostic-manifest.json').relative_to(ROOT).as_posix())),encoding='utf-8')
        print(json.dumps(dict(status='pass',scope=m['scope'],release_claim=False,modes=len(m['runs']))))
    except (OSError,ValueError,subprocess.SubprocessError):
        print(json.dumps(dict(status='fail',reason='p04a_diagnostic_failed')));raise SystemExit(1)
