"""Closed P04a evidence reconstruction; native success requires fresh isolated replay."""
import json,secrets,shutil,subprocess,sys,tempfile
from pathlib import Path
from ct import inspect_pe
from prepare_nvcc_probe import audit_probe,digest
from run_validation import source_fingerprint
from run_p04a_smoke import SOURCES,CASES,compiler_commands,rust_commands
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from p04a_runtime_check import expected,validate
MODES=('positive','positive_fresh','noop','missing','forwarded','old_missing','old_forwarded','unsupported')
ARTIFACTS=('host.exe','negative.exe','control.exe','ct_cuda.dll','ct_cudart.dll','noop.dll','missing.dll','ct_foreign.dll','forwarded.dll')
DIRECT=dict(status='pass',scope='direct_driver_globals',ordered_calls=100,module_lifecycles=1000,contexts=2)


def exact(a,b):
    if type(a) is not type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in b)
    if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    return a==b


def verify_mode(mode,value,seed):
    if mode not in MODES or type(seed) is not int or not 1<=seed<=999990:return ['invalid global mode/seed']
    if mode.startswith('old_'):return [] if value==b'vector results correct' else ['old-path result mismatch']
    if mode in ('positive','positive_fresh'):return validate(value,seed)
    if mode=='noop':
        want=expected(seed);initial=[((seed*3+i*11)^0x13579bdf)&0xffffffff for i in range(145)]
        want['runs']=[initial]*100
    elif mode in ('missing','forwarded'):want=dict(error=35,memory_roundtrip=1)
    else:want=dict(seed=seed,mode='used_global',errors=[801],runs=[],main_entered=1)
    return [] if exact(value,want) else ['global control result mismatch']


def expected_payloads(mode):
    app='control.exe' if mode in ('missing','forwarded') else 'negative.exe' if mode=='unsupported' else 'compressed.exe' if mode.startswith('old_') else 'host.exe'
    provider='noop.dll' if mode=='noop' else mode.removeprefix('old_')+'.dll' if mode in ('missing','forwarded','old_missing','old_forwarded') else 'ct_cuda.dll'
    roles={app:'producer_application' if mode.startswith('old_') else app,'nvcuda.dll':provider,'cudart64_12.dll':'ct_cudart.dll'}
    if mode not in ('positive','positive_fresh','unsupported'):roles['ct_underlying.dll']='ct_cuda.dll'
    if mode in ('missing','forwarded'):roles['global_runtime.fatbin']='image'
    if mode in ('forwarded','old_forwarded'):roles['ct_foreign.dll']='ct_foreign.dll'
    return roles


def arguments(mode,seed):
    return ['used_global',str(seed)] if mode=='unsupported' else [] if mode.startswith('old_') or mode in ('missing','forwarded') else [str(seed)]


def local(root,name):
    if not isinstance(name,str):raise ValueError('invalid path')
    p=(root/name).resolve()
    if not p.is_relative_to((root/'.cache/p04a-smoke').resolve()):raise ValueError('artifact escape')
    return p


def file_item(root,item):
    if not isinstance(item,dict) or set(item)!={'path','sha256'}:raise ValueError('artifact schema')
    p=local(root,item['path'])
    if digest(p)!=item['sha256']:raise ValueError('artifact hash mismatch')
    return p


def output_value(out,mode):
    if out.stat().st_size>1024*1024:raise ValueError('output budget')
    raw=out.read_bytes()
    return raw.strip() if mode.startswith('old_') else json.loads(raw)


def _check(path,root):
    m=json.loads(Path(path).read_bytes())
    keys={'schema_version','scope','release_claim','source_tree','inputs','producer','commands','rust_commands','artifacts','compiler_outputs','runs','direct_driver'}
    if set(m)!=keys or type(m['schema_version']) is not int or m['schema_version']!=1 or m['scope']!='diagnostic_p04a_globals' or m['release_claim'] is not False:raise ValueError('global schema')
    if m['source_tree']!=source_fingerprint(root) or m['inputs']!={n:digest(root/n) for n in SOURCES}:raise ValueError('global source identity')
    producer=m['producer']
    if set(producer)!={'path','sha256'}:raise ValueError('producer schema')
    p=(root/producer['path']).resolve()
    if not p.is_relative_to(root/'.cache') or digest(p)!=producer['sha256'] or audit_probe(p):raise ValueError('producer identity')
    base=json.loads(p.read_bytes())
    if base['host']['profile']!='diagnostic':raise ValueError('host profile mismatch')
    if set(m['artifacts'])!=set(ARTIFACTS):raise ValueError('artifact set')
    files={name:file_item(root,item) for name,item in m['artifacts'].items()}
    folder=files['host.exe'].parent
    if any(f.parent!=folder or f.name!=name for name,f in files.items()):raise ValueError('artifact roles')
    for target,name in [('driver-target','ct_cuda.dll'),('runtime-target','ct_cudart.dll')]:
        if digest(folder/target/'debug'/name)!=digest(files[name]):raise ValueError('Rust build artifact changed')
    if m['commands']!=compiler_commands(p,folder,base,root) or m['rust_commands']!=rust_commands(folder):raise ValueError('build recipe mismatch')
    for source in SOURCES[:2]:
        if digest(folder/Path(source).name)!=m['inputs'][source]:raise ValueError('compiled source snapshot')
    outputs={f'keep-{stem}/{stem}{suffix}' for stem,_,_ in CASES for suffix in ('.ptx','.fatbin','.cudafe1.stub.c')}
    outputs |= {f'keep-{stem}/{exe}_dlink.fatbin' for stem,exe,default in CASES if default}
    if set(m['compiler_outputs'])!=outputs:raise ValueError('compiler output roles')
    for name,sha in m['compiler_outputs'].items():
        if digest(folder/name)!=sha:raise ValueError('compiler output changed')
    text=(folder/'keep-global_runtime/global_runtime.ptx').read_text(encoding='utf-8')
    stub=(folder/'keep-global_runtime/global_runtime.cudafe1.stub.c').read_text(encoding='utf-8')
    if not all(n in text for n in ('ct_counter','ct_zero','ct_unused','ld.volatile.global','st.volatile.global')) or '__cudaRegisterVar' not in stub:raise ValueError('global compiler metadata absent')
    for name,f in files.items():inspect_pe(f.read_bytes(),dll=name.endswith('.dll'),runtime=name in ('host.exe','negative.exe'))
    imports=inspect_pe(files['host.exe'].read_bytes(),runtime=True)['imports']
    symbols={s for i in imports if i['library'].lower()=='cudart64_12.dll' for s in i['symbols']}
    if not {'__cudaRegisterVar','cudaLaunchKernel','__cudaRegisterFatBinary','__cudaRegisterFunction'}<=symbols:raise ValueError('genuine variable imports absent')
    files['producer_application']=p.parent/'compressed.exe';files['image']=folder/'keep-global_runtime/global_runtime.fatbin'
    if not isinstance(m['runs'],list) or [r.get('mode') for r in m['runs']]!=list(MODES):raise ValueError('native modes missing/duplicate')
    for row in m['runs']:
        if set(row)!={'mode','seed','exit_code','stdout','stderr','bundle','payloads'} or type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('execution record schema')
        mode,seed=row['mode'],row['seed'];roles=expected_payloads(mode);bundle=local(root,row['bundle'])
        hashes={name:digest(files[role]) for name,role in roles.items()}
        if row['payloads']!=hashes or {f.name for f in bundle.iterdir()}!=set(roles):raise ValueError('bundle role set')
        if any(digest(bundle/name)!=sha for name,sha in hashes.items()):raise ValueError('bundle bytes changed')
        out=file_item(root,row['stdout']);err=file_item(root,row['stderr'])
        if out!=folder/(mode+'.stdout') or err!=folder/(mode+'.stderr') or err.read_bytes():raise ValueError('native logs')
        if verify_mode(mode,output_value(out,mode),seed):raise ValueError('native oracle mismatch')
    if m['runs'][0]['seed']==m['runs'][1]['seed']:raise ValueError('fresh seed was reused')
    row=m['direct_driver']
    if set(row)!={'exit_code','stdout','stderr'} or type(row['exit_code']) is not int or row['exit_code']!=0:raise ValueError('Driver execution schema')
    out=file_item(root,row['stdout']);err=file_item(root,row['stderr'])
    if out!=folder/'driver.stdout' or err!=folder/'driver.stderr' or err.read_bytes() or not exact(output_value(out,'driver'),DIRECT):raise ValueError('Driver result mismatch')
    return m,folder,files


def _replay_driver(root,files):
    r=subprocess.run([sys.executable,str(root/'tests/p04a_driver_check.py'),'--dll',str(files['ct_cuda.dll'])],cwd=root,capture_output=True,timeout=180)
    if r.returncode or r.stderr or not exact(json.loads(r.stdout),DIRECT):raise ValueError('Driver fresh replay')


def audit_manifest(path,root=ROOT,*,execute=False):
    try:
        m,folder,files=_check(path,root)
        if execute:
            for mode in MODES:
                seed=secrets.randbelow(999990)+1;roles=expected_payloads(mode)
                with tempfile.TemporaryDirectory(dir=root/'.cache/p04a-smoke') as tmp:
                    cwd=Path(tmp)
                    for name,role in roles.items():shutil.copyfile(files[role],cwd/name)
                    application='control.exe' if mode in ('missing','forwarded') else 'negative.exe' if mode=='unsupported' else 'compressed.exe' if mode.startswith('old_') else 'host.exe'
                    r=subprocess.run([str(cwd/application)]+arguments(mode,seed),cwd=cwd,capture_output=True,timeout=120)
                    if r.returncode or r.stderr or len(r.stdout)>1024*1024:raise ValueError('native replay failed')
                    value=r.stdout.strip() if mode.startswith('old_') else json.loads(r.stdout)
                    if verify_mode(mode,value,seed):raise ValueError('replay oracle mismatch')
            _replay_driver(root,files)
            _check(path,root) # Rehash original inputs after executing copies.
        return []
    except (OSError,ValueError,TypeError,KeyError,AttributeError,subprocess.SubprocessError):return ['global evidence unavailable or changed']
