"""Build and observe genuine synchronous CUDA symbol operations; local diagnostic only."""
import argparse,json,os,secrets,shutil,subprocess,sys,uuid
from pathlib import Path
from prepare_nvcc_default import host_environment
from prepare_nvcc_probe import digest
from run_validation import source_fingerprint
from ct import prepare_bundle,inspect_pe
from run_p04a_smoke import compiler_commands as old_commands,run,rust_commands
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from p04b_symbol_check import validate,validate_noop
SOURCES=['tests/fixtures/p04b/symbol_runtime.cu','tests/p04b_symbol_check.py',
 'tests/runtime_symbol_reference_abi.cpp','tests/runtime_symbol_declared_abi.cpp',
 'tests/runtime_symbol_native_abi.cpp','tests/runtime_symbol_probe.hpp',
 'include/ct_cudart.h','include/ct_cuda.h','tests/p04a_noop_driver.c','tests/p09a_noop_driver.c',
 'tests/p04a_driver_control.def','tests/p09a_driver_control.def','tests/p04a_forwarded_global.def',
 'tests/p04a_foreign_global.c','scripts/run_p04b_smoke.py','scripts/run_p04a_smoke.py',
 'scripts/prepare_nvcc_default.py','scripts/prepare_nvcc_probe.py','scripts/p04b_evidence.py']
ARTIFACTS={'host':'host.exe','reference':'reference.exe','declared':'declared.exe','native':'native.exe',
 'driver':'ct_cuda.dll','runtime':'ct_cudart.dll','noop':'noop.dll','missing':'missing.dll',
 'forwarded':'forwarded.dll','foreign':'ct_foreign.dll'}
ORDERS={'positive_symbol_first':0,'positive_launch_first':1,'fresh_symbol_first':0,'fresh_launch_first':1,'noop':0}
MODES=(*ORDERS,'retire','missing','forwarded')
ABI_EXPECTED=b'SYMBOL_ABI 4 8 8 4\n13 21 1 2 3 4\n'
def compiler_commands(producer,folder,base,root=ROOT):
    toolkit=producer.resolve().parent
    compiler=Path(base['host']['tools']['cl.exe']['path'])
    commands=[dict(name='host',argv=[str(toolkit/'toolkit/bin/nvcc.exe'),'--std=c++17','--compiler-bindir',str(compiler.parent),'-allow-unsupported-compiler','-I',str(toolkit/'stl'),'-Xcompiler','/utf-8','--cudart=shared','--keep','--keep-dir','keep-symbol_runtime','--generate-code','arch=compute_52,code=compute_52','symbol_runtime.cu','-o','host.exe'])]
    for role in ('reference','declared','native'):
        commands.append(dict(name=role,argv=[str(compiler),'/nologo','/W4','/WX','/EHsc','/Gy','/std:c++17','/utf-8','/external:W0','/external:I'+str(toolkit/'toolkit/include'),str(root/'tests'/('runtime_symbol_'+role+'_abi.cpp')),'/Fo'+str(folder/(role+'.obj')),'/Fe'+str(folder/(role+'.exe')),'/link','/OPT:REF']))
    commands += [c for c in old_commands(producer,folder,base,root) if c['name'] in ('noop','missing','ct_foreign','forwarded')]
    return commands
def build(producer,folder):
    folder.mkdir(parents=True,exist_ok=False)
    base,env=host_environment(producer,folder)
    shutil.copyfile(ROOT/SOURCES[0],folder/'symbol_runtime.cu')
    (folder/'keep-symbol_runtime').mkdir()
    commands=compiler_commands(producer,folder,base)
    for command in commands:run(command['argv'],folder,env,command['name'])
    build_env=dict(os.environ,CARGO_INCREMENTAL='0')
    for command in rust_commands(folder):
        build_env['CARGO_TARGET_DIR']=str(folder/command['name'])
        result=subprocess.run(command['argv'],cwd=ROOT,env=build_env,capture_output=True,timeout=180)
        (folder/(command['name']+'.log')).write_bytes(result.stdout+result.stderr)
        if result.returncode:raise ValueError('Rust build failed')
        shutil.copyfile(folder/command['name']/'debug'/command['output'],folder/command['output'])
    return commands
def control_expected(mode):
    return ('SYMBOL_NATIVE '+mode+(' 26 123 13 1\n' if mode=='retire' else ' 26 35 123\n')).encode('ascii')
def payload_roles(mode):
    if mode in ORDERS:
        roles={'host.exe':'host','nvcuda.dll':'noop' if mode=='noop' else 'driver','cudart64_12.dll':'runtime'}
        if mode=='noop':roles['ct_underlying.dll']='driver'
    else:
        roles={'native.exe':'native','nvcuda.dll':'driver' if mode=='retire' else mode,'cudart64_12.dll':'runtime','symbol_runtime.fatbin':'image'}
        if mode!='retire':roles['ct_underlying.dll']='driver'
        if mode=='forwarded':roles['ct_foreign.dll']='foreign'
    return roles
def capture(folder,producer,commands,*,abi_only=False):
    def item(p):return dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p))
    files={role:folder/name for role,name in ARTIFACTS.items()}
    files['image']=folder/'keep-symbol_runtime/symbol_runtime.fatbin'
    manifest=dict(schema_version=1,scope='diagnostic_p04b_symbol_abi' if abi_only else 'diagnostic_p04b_symbols',release_claim=False,
        source_tree=source_fingerprint(ROOT),inputs={n:digest(ROOT/n) for n in SOURCES},
        producer=item(producer),commands=commands,rust_commands=rust_commands(folder),
        artifacts={r:item(p) for r,p in files.items() if r!='image'},
        compiler_outputs={str(p.relative_to(folder)).replace('\\','/'):digest(p) for p in (folder/'keep-symbol_runtime').iterdir() if p.suffix in ('.ptx','.fatbin') or p.name.endswith('.cudafe1.stub.c')},abi=[],runs=[])
    for role in ('reference','declared'):
        result=subprocess.run([str(files[role])],cwd=folder,capture_output=True,timeout=30)
        out=folder/(role+'.stdout');err=folder/(role+'.stderr');out.write_bytes(result.stdout);err.write_bytes(result.stderr)
        if result.returncode or result.stderr or result.stdout.replace(b'\r\n',b'\n')!=ABI_EXPECTED:raise ValueError('symbol ABI declaration mismatch')
        manifest['abi'].append(dict(role=role,exit_code=result.returncode,stdout=item(out),stderr=item(err)))
    # A separate directory with no adjacent Driver proves pure preflight does not require it.
    pure=folder/'pure';pure.mkdir();shutil.copyfile(files['native'],pure/'native.exe');shutil.copyfile(files['runtime'],pure/'cudart64_12.dll')
    result=subprocess.run([str(pure/'native.exe'),str(pure/'cudart64_12.dll'),'pure'],cwd=pure,capture_output=True,timeout=30)
    out=folder/'pure.stdout';err=folder/'pure.stderr';out.write_bytes(result.stdout);err.write_bytes(result.stderr)
    if result.returncode or result.stderr or result.stdout.replace(b'\r\n',b'\n')!=b'SYMBOL_NATIVE pure 26 13 21 801\n':raise ValueError('symbol pure typed mismatch')
    manifest['abi'].append(dict(role='pure',exit_code=result.returncode,stdout=item(out),stderr=item(err)))
    seeds=set()
    for mode in (() if abi_only else MODES):
        seed=secrets.randbelow(999990)+1
        while seed in seeds:seed=secrets.randbelow(999990)+1
        seeds.add(seed);order=ORDERS.get(mode,0);roles=payload_roles(mode)
        application=files['host' if mode in ORDERS else 'native'];provider=files[roles['nvcuda.dll']]
        assets=[files['image']] if mode not in ORDERS else []
        bundle,_=prepare_bundle(application,provider,assets,folder/'runs',runtime_dll=files['runtime'])
        for name,role in roles.items():
            if not (bundle/name).exists():shutil.copyfile(files[role],bundle/name)
        args=[str(seed),str(order)] if mode in ORDERS else [str(bundle/'cudart64_12.dll'),mode]
        result=subprocess.run([str(bundle/application.name)]+args,cwd=bundle,capture_output=True,timeout=180)
        out=folder/(mode+'.stdout');err=folder/(mode+'.stderr');out.write_bytes(result.stdout);err.write_bytes(result.stderr)
        if result.returncode or result.stderr:raise ValueError('native symbol mode failed: '+mode)
        if mode in ORDERS:
            check=validate_noop if mode=='noop' else validate
            if check(json.loads(result.stdout),seed,order):raise ValueError('symbol numerical control: '+mode)
        elif result.stdout.replace(b'\r\n',b'\n')!=control_expected(mode):raise ValueError('symbol provider/retire control: '+mode)
        manifest['runs'].append(dict(mode=mode,seed=seed,order=order,exit_code=result.returncode,
            stdout=item(out),stderr=item(err),bundle=bundle.relative_to(ROOT).as_posix(),payloads={name:digest(files[role]) for name,role in roles.items()}))
    (folder/'diagnostic-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--producer',type=Path,default=ROOT/'.cache/p09a2-producer/manifest.json');parser.add_argument('--abi-only',action='store_true');args=parser.parse_args()
    folder=ROOT/'.cache/p04b-smoke'/uuid.uuid4().hex
    pointer=ROOT/'.cache'/('p04b-symbol-abi-latest.json' if args.abi_only else 'p04b-symbol-latest.json');pointer.unlink(missing_ok=True)
    try:
        commands=build(args.producer.resolve(),folder);capture(folder,args.producer.resolve(),commands,abi_only=args.abi_only)
        from p04b_evidence import audit_manifest
        manifest=folder/'diagnostic-manifest.json'
        if audit_manifest(manifest,ROOT,execute=True,abi_only=args.abi_only):raise ValueError('symbol evidence reconstruction failed')
        pointer.write_text(json.dumps(dict(manifest=manifest.relative_to(ROOT).as_posix())),encoding='utf-8')
        print(json.dumps(dict(status='pass',scope='diagnostic_p04b_symbol_abi' if args.abi_only else 'diagnostic_p04b_symbols',modes=[] if args.abi_only else list(MODES),evidence_qualification=True,release_claim=False)))
    except (OSError,ValueError,subprocess.SubprocessError):
        print(json.dumps(dict(status='fail',reason='symbol_diagnostic_failed',local_diagnostics=folder.relative_to(ROOT).as_posix())));raise SystemExit(1)
