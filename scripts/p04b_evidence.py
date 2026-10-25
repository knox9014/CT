"""Closed Runtime-symbol proof: pinned inputs, Cargo outputs and isolated fresh replay."""
import json,secrets,shutil,subprocess,tempfile
from pathlib import Path
from ct import inspect_pe
from prepare_nvcc_probe import audit_probe,digest
from run_validation import source_fingerprint
from run_p04b_smoke import ROOT,SOURCES,ARTIFACTS,MODES,ORDERS,ABI_EXPECTED,compiler_commands,rust_commands,payload_roles,control_expected
from p04b_symbol_check import validate,validate_noop
OUTPUTS={f'keep-symbol_runtime/{name}' for name in ('symbol_runtime.ptx','symbol_runtime.fatbin','symbol_runtime.cudafe1.stub.c','host_dlink.fatbin')}
PURE=b'SYMBOL_NATIVE pure 26 13 21 801\n'
def local(root,name):
    if not isinstance(name,str):raise ValueError('path type')
    p=(root/name).resolve()
    if not p.is_relative_to((root/'.cache/p04b-smoke').resolve()):raise ValueError('artifact escape')
    return p
def item(root,row):
    if not isinstance(row,dict) or set(row)!={'path','sha256'}:raise ValueError('artifact schema')
    p=local(root,row['path'])
    if digest(p)!=row['sha256']:raise ValueError('artifact bytes')
    return p
def verify(mode,raw,seed,order):
    if type(seed) is not int or not 1<=seed<=999990 or type(order) is not int or order!=ORDERS.get(mode,0):raise ValueError('mode parameters')
    if mode in ORDERS:
        check=validate_noop if mode=='noop' else validate
        if check(json.loads(raw),seed,order):raise ValueError('numerical/guard/input/state evidence')
    elif raw.replace(b'\r\n',b'\n')!=control_expected(mode):raise ValueError('typed control evidence')
def _check(path,root,abi_only):
    m=json.loads(Path(path).read_bytes())
    fields={'schema_version','scope','release_claim','source_tree','inputs','producer','commands','rust_commands','artifacts','compiler_outputs','abi','runs'}
    if not isinstance(m,dict) or set(m)!=fields or type(m['schema_version']) is not int or m['schema_version']!=1 or m['release_claim'] is not False:raise ValueError('symbol schema')
    if m['scope']!=('diagnostic_p04b_symbol_abi' if abi_only else 'diagnostic_p04b_symbols'):raise ValueError('symbol scope')
    if m['source_tree']!=source_fingerprint(root) or m['inputs']!={n:digest(root/n) for n in SOURCES}:raise ValueError('symbol source identity')
    producer=m['producer']
    if not isinstance(producer,dict) or set(producer)!={'path','sha256'}:raise ValueError('producer schema')
    p=(root/producer['path']).resolve()
    if not p.is_relative_to(root/'.cache') or digest(p)!=producer['sha256'] or audit_probe(p):raise ValueError('producer identity')
    base=json.loads(p.read_bytes())
    if base['host']['profile']!='diagnostic':raise ValueError('host profile')
    if set(m['artifacts'])!=set(ARTIFACTS):raise ValueError('artifact roles')
    files={role:item(root,row) for role,row in m['artifacts'].items()}
    folder=files['host'].parent
    if any(f.parent!=folder or f.name!=ARTIFACTS[role] for role,f in files.items()):raise ValueError('artifact location')
    for target,role in [('driver-target','driver'),('runtime-target','runtime')]:
        if digest(folder/target/'debug'/ARTIFACTS[role])!=digest(files[role]):raise ValueError('actual Cargo output')
    if m['commands']!=compiler_commands(p,folder,base,root) or m['rust_commands']!=rust_commands(folder):raise ValueError('compiler/Rust recipe')
    if digest(folder/'symbol_runtime.cu')!=m['inputs'][SOURCES[0]]:raise ValueError('compiled source snapshot')
    if set(m['compiler_outputs'])!=OUTPUTS:raise ValueError('compiler output set')
    for name,sha in m['compiler_outputs'].items():
        if digest(folder/name)!=sha:raise ValueError('compiler output bytes')
    text=(folder/'keep-symbol_runtime/symbol_runtime.ptx').read_text(encoding='utf-8');stub=(folder/'keep-symbol_runtime/symbol_runtime.cudafe1.stub.c').read_text(encoding='utf-8')
    if not all(s in text for s in ('ct_counter','ct_other','ld.volatile.global','st.volatile.global')) or '__cudaRegisterVar' not in stub:raise ValueError('compiler global metadata')
    for role,f in files.items():inspect_pe(f.read_bytes(),dll=f.suffix=='.dll',runtime=role=='host')
    imports=inspect_pe(files['host'].read_bytes(),runtime=True)['imports']
    symbols={s for row in imports if row['library'].lower()=='cudart64_12.dll' for s in row['symbols']}
    if not {'__cudaRegisterVar','__cudaRegisterFatBinary','__cudaRegisterFunction','cudaLaunchKernel','cudaGetSymbolAddress','cudaGetSymbolSize','cudaMemcpyToSymbol','cudaMemcpyFromSymbol'}<=symbols:raise ValueError('genuine imports')
    if not isinstance(m['abi'],list) or [r.get('role') for r in m['abi']]!=['reference','declared','pure']:raise ValueError('ABI role set')
    for row in m['abi']:
        if set(row)!={'role','exit_code','stdout','stderr'} or type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('ABI schema')
        role=row['role'];out=item(root,row['stdout']);err=item(root,row['stderr'])
        if out!=folder/(role+'.stdout') or err!=folder/(role+'.stderr') or err.read_bytes() or out.read_bytes().replace(b'\r\n',b'\n')!=(PURE if role=='pure' else ABI_EXPECTED):raise ValueError('ABI observations')
    pure=folder/'pure'
    if {p.name for p in pure.iterdir()}!={'native.exe','cudart64_12.dll'} or digest(pure/'native.exe')!=digest(files['native']) or digest(pure/'cudart64_12.dll')!=digest(files['runtime']):raise ValueError('pure bundle')
    files['image']=folder/'keep-symbol_runtime/symbol_runtime.fatbin'
    modes=[] if abi_only else list(MODES)
    if not isinstance(m['runs'],list) or [r.get('mode') for r in m['runs']]!=modes:raise ValueError('native modes')
    seeds=set()
    for row in m['runs']:
        if set(row)!={'mode','seed','order','exit_code','stdout','stderr','bundle','payloads'} or type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('native schema')
        mode=row['mode'];bundle=local(root,row['bundle']);roles=payload_roles(mode)
        if row['payloads']!={n:digest(files[r]) for n,r in roles.items()} or {f.name for f in bundle.iterdir()}!=set(roles):raise ValueError('native payload role set')
        if any(digest(bundle/n)!=digest(files[r]) for n,r in roles.items()):raise ValueError('native payload bytes')
        out=item(root,row['stdout']);err=item(root,row['stderr'])
        if out!=folder/(mode+'.stdout') or err!=folder/(mode+'.stderr') or err.read_bytes() or out.stat().st_size>1024*1024:raise ValueError('native raw observations')
        verify(mode,out.read_bytes(),row['seed'],row['order'])
        if row['seed'] in seeds:raise ValueError('reused fresh seed')
        seeds.add(row['seed'])
    return m,folder,files
def audit_manifest(path,root=ROOT,*,execute=False,abi_only=False):
    try:
        m,folder,files=_check(path,root,abi_only)
        if execute:
            with tempfile.TemporaryDirectory(dir=root/'.cache/p04b-smoke') as directory:
                work=Path(directory)
                for role in ('reference','declared','pure'):
                    bundle=work/role;bundle.mkdir()
                    if role=='pure':
                        shutil.copyfile(files['native'],bundle/'native.exe');shutil.copyfile(files['runtime'],bundle/'cudart64_12.dll')
                        argv=[str(bundle/'native.exe'),str(bundle/'cudart64_12.dll'),'pure']
                    else:
                        shutil.copyfile(files[role],bundle/(role+'.exe'));argv=[str(bundle/(role+'.exe'))]
                    result=subprocess.run(argv,cwd=bundle,capture_output=True,timeout=30)
                    if result.returncode or result.stderr or result.stdout.replace(b'\r\n',b'\n')!=(PURE if role=='pure' else ABI_EXPECTED):raise ValueError('ABI fresh replay')
                seeds={row['seed'] for row in m['runs']}
                for row in m['runs']:
                    mode=row['mode'];bundle=work/mode;bundle.mkdir()
                    for name,role in payload_roles(mode).items():shutil.copyfile(files[role],bundle/name)
                    seed=secrets.randbelow(999990)+1
                    while seed in seeds:seed=secrets.randbelow(999990)+1
                    seeds.add(seed)
                    argv=[str(bundle/'host.exe'),str(seed),str(row['order'])] if mode in ORDERS else [str(bundle/'native.exe'),str(bundle/'cudart64_12.dll'),mode]
                    result=subprocess.run(argv,cwd=bundle,capture_output=True,timeout=180)
                    if result.returncode or result.stderr or len(result.stdout)>1024*1024:raise ValueError('native fresh replay')
                    verify(mode,result.stdout,seed,row['order'])
            # Recheck all original observations and binaries after isolated execution.
            _check(path,root,abi_only)
        return []
    except (OSError,ValueError,KeyError,TypeError,AttributeError,subprocess.SubprocessError):return ['symbol evidence invalid or unavailable']
def audit_abi(path,root=ROOT,*,execute=False):return audit_manifest(path,root,execute=execute,abi_only=True)
