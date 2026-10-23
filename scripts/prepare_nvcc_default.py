"""Authenticated default device-runtime producer and CPU-only constructor observations."""
import argparse,json,os,shutil,struct,subprocess
from pathlib import Path
from prepare_nvcc_probe import audit_probe,digest,normalize_env,decode_host_env
ROOT=Path(__file__).resolve().parents[1]
SOURCE='tests/fixtures/p09a2/vector.cu'
OBSERVER='tests/p09a2c_registration_observer.cpp'

def compiler_args(output,base,host):
    args=[str(base/'toolkit/bin/nvcc.exe'),'--compiler-bindir',str(Path(host['tools']['cl.exe']['path']).parent),'-Xcompiler','/utf-8','--cudart=shared','--keep','--keep-dir','keep','--generate-code','arch=compute_52,code=compute_52','vector.cu','-o','default.exe']
    if host['profile']=='diagnostic':args+=['-allow-unsupported-compiler','-I',str(base/'stl')]
    return args

def host_environment(base_manifest,output):
    base_manifest=Path(base_manifest).resolve()
    if audit_probe(base_manifest):raise ValueError('unverified base producer')
    base=json.loads(base_manifest.read_bytes());host=base['host']
    finder=Path(os.environ['ProgramFiles(x86)'])/'Microsoft Visual Studio/Installer/vswhere.exe'
    installed=subprocess.check_output([str(finder),'-latest','-products','*','-property','installationPath'],text=True).strip()
    vcvars=Path(installed)/'VC/Auxiliary/Build/vcvars64.bat'
    if vcvars.resolve()!=Path(host['vcvars']['path']).resolve() or digest(vcvars)!=host['vcvars']['sha256']:raise ValueError('host selection changed')
    script=output/'host-env.cmd'
    script.write_text('@echo off\ncall "'+str(vcvars)+'" >nul\nif errorlevel 1 exit /b 1\nset\n',encoding='utf-8')
    run=subprocess.run(['cmd.exe','/d','/u','/c',str(script)],capture_output=True,check=True,timeout=90)
    env=normalize_env(decode_host_env(run.stdout));compiler=Path(host['tools']['cl.exe']['path']).parent
    previous=next((v for k,v in env.items() if k.upper()=='PATH'),'');env={k:v for k,v in env.items() if k.upper()!='PATH'};env['PATH']=str(compiler)+os.pathsep+previous
    for tool in ('cl.exe','link.exe'):
        if Path(shutil.which(tool,path=env['PATH'])).resolve()!=Path(host['tools'][tool]['path']).resolve():raise ValueError('host tool differs')
    return base,env

def validate_observations(rows):
    try:
        fields={'wrapper':{'kind','version'},'image':{'kind','index','size'},'linked':{'kind','count'},'function':{'kind','limit','optional','equal','host'},'variable':{'kind','host','external','size','constant','global','address','name'},'end':{'kind'},'retire':{'kind'}}
        if any(not isinstance(r,dict) or r.get('kind') not in fields or set(r)!=fields[r['kind']] for r in rows):return ['default observer schema']
        versions=[r['version'] for r in rows if r['kind']=='wrapper']
        images=[r for r in rows if r['kind']=='image'];variables=[r for r in rows if r['kind']=='variable'];functions=[r for r in rows if r['kind']=='function']
        if versions!=[1,2] or len(images)!=3 or [r['index'] for r in images]!=[0,1,2] or images[1]['size']!=16:return ['default wrapper observations']
        if [r['count'] for r in rows if r['kind']=='linked']!=[1] or len(variables)!=11 or len(functions)!=33:return ['default registration observations']
        if len([r for r in rows if r['kind']=='end'])!=2 or len([r for r in rows if r['kind']=='retire'])!=2:return ['default lifetime observations']
        if any(r!={'kind':'function','limit':-1,'optional':0,'equal':1,'host':1} for r in functions):return ['default function metadata']
        for r in variables:
            if set(r)!={'kind','host','external','size','constant','global','address','name'} or r['host']!=1 or (r['external'],r['constant'],r['global'])!=(0,0,0) or not 1<=r['size']<=16777216:return ['default variable metadata']
            a=bytes.fromhex(r['address']);b=bytes.fromhex(r['name'])
            if not a or len(a)>1024 or a!=b or not a.isascii() or b'\0' in a:return ['default variable names']
        if any(r['kind'] not in ('wrapper','image','linked','variable','function','end','retire') for r in rows):return ['default observer event']
        return []
    except (ValueError,KeyError,TypeError):return ['invalid default observations']

def raw_info(path):
    b=Path(path).read_bytes()
    if len(b)<16 or struct.unpack_from('<IHH',b)!=(0xba55ed50,1,16) or struct.unpack_from('<Q',b,8)[0]!=len(b)-16 or len(b)>16777216:raise ValueError('raw image')
    o=16;records=[]
    while o<len(b):
        k,v,h,n=struct.unpack_from('<HHIQ',b,o)
        if v!=0x101 or k not in (1,2) or not 64<=h<=4096 or h%8 or not n or n%8 or o+h+n>len(b) or len(records)==256:raise ValueError('raw record')
        records.append(k);o+=h+n
    return records

def artifacts(output):
    fixed=['default.exe','observer.dll','observe/application.exe','observe/cudart64_12.dll','observe/stdout.jsonl','observe/stderr.txt','vector.cu','observer.cpp']
    fixed += ['keep/vector'+s for s in ('.fatbin','.ptx','.cudafe1.stub.c')]
    fixed += ['keep/default_dlink'+s for s in ('.fatbin','.fatbin.c','.reg.c')]
    fixed += ['observe/raw-'+str(i)+'.bin' for i in range(3)]
    return {n:digest(output/n) for n in fixed}

def audit_default_producer(path,root=ROOT):
    try:
        path=Path(path).resolve()
        if not path.is_relative_to(root/'.cache/p09a2c-producer'):return ['default producer escape']
        m=json.loads(path.read_bytes())
        if set(m)!={'schema_version','base_producer','source','commands','host_profile','artifacts','observations'} or m['schema_version']!=1:return ['default producer schema']
        ref=m['base_producer'];base=(root/ref['path']).resolve()
        if set(ref)!={'path','sha256'} or not base.is_relative_to(root/'.cache') or digest(base)!=ref['sha256'] or audit_probe(base):return ['default base producer']
        host=json.loads(base.read_bytes())['host'];out=path.parent
        if m['host_profile']!=host['profile'] or m['source']!={SOURCE:digest(root/SOURCE),OBSERVER:digest(root/OBSERVER)}:return ['default source/qualification']
        if m['commands']!=commands(out,base.parent,host):return ['default compiler flags']
        if m['artifacts']!=artifacts(out) or digest(out/'vector.cu')!=digest(root/SOURCE) or digest(out/'observer.cpp')!=digest(root/OBSERVER):return ['default artifacts changed']
        if digest(out/'default.exe')!=digest(out/'observe/application.exe') or digest(out/'observer.dll')!=digest(out/'observe/cudart64_12.dll'):return ['default bundle mismatch']
        rows=[json.loads(line) for line in (out/'observe/stdout.jsonl').read_text().splitlines()]
        if m['observations']!={'exit_code':11,'rows':rows} or validate_observations(rows) or (out/'observe/stderr.txt').read_bytes():return ['default observations changed']
        if any(r['size']!=(out/('observe/raw-'+str(r['index'])+'.bin')).stat().st_size for r in rows if r['kind']=='image'):return ['default observed size mismatch']
        if raw_info(out/'observe/raw-0.bin')!=[1] or raw_info(out/'observe/raw-1.bin')!=[] or raw_info(out/'observe/raw-2.bin')!=[2]*9:return ['default raw shape']
        if digest(out/'observe/raw-0.bin')!=digest(out/'keep/vector.fatbin') or digest(out/'observe/raw-1.bin')!=digest(out/'keep/default_dlink.fatbin'):return ['default raw source mismatch']
        return []
    except (OSError,ValueError,KeyError,TypeError,struct.error):return ['default producer unavailable']

def commands(out,base,host):
    return {'cuda':compiler_args(out,base,host),'observer':[host['tools']['cl.exe']['path'],'/nologo','/W4','/WX','/EHsc','/LD','/std:c++17','/utf-8','/external:W0','/external:I'+str(base/'toolkit/include'),'observer.cpp','/Foobserver.obj','/Feobserver.dll']}

def prepare(base_path,out):
    out=out.resolve();base_path=base_path.resolve()
    if not out.is_relative_to(ROOT/'.cache/p09a2c-producer'):raise ValueError('default output must stay in configured cache')
    out.mkdir(parents=True,exist_ok=True);base,env=host_environment(base_path,out)
    shutil.copyfile(ROOT/SOURCE,out/'vector.cu');shutil.copyfile(ROOT/OBSERVER,out/'observer.cpp');(out/'keep').mkdir(exist_ok=True)
    argv=commands(out,base_path.parent,base['host'])
    for mode,command in argv.items():
        run=subprocess.run(command,cwd=out,env=env,capture_output=True,timeout=120);(out/(mode+'.log')).write_bytes(run.stdout+run.stderr)
        if run.returncode:raise ValueError('default compile failed: '+mode)
    bundle=out/'observe';bundle.mkdir(exist_ok=True);shutil.copyfile(out/'default.exe',bundle/'application.exe');shutil.copyfile(out/'observer.dll',bundle/'cudart64_12.dll')
    run=subprocess.run([str(bundle/'application.exe')],cwd=bundle,capture_output=True,timeout=30);(bundle/'stdout.jsonl').write_bytes(run.stdout);(bundle/'stderr.txt').write_bytes(run.stderr)
    rows=[json.loads(line) for line in run.stdout.splitlines()]
    if run.returncode!=11 or run.stderr or validate_observations(rows):raise ValueError('default constructor observation failed')
    m={'schema_version':1,'base_producer':{'path':base_path.relative_to(ROOT).as_posix(),'sha256':digest(base_path)},'source':{SOURCE:digest(ROOT/SOURCE),OBSERVER:digest(ROOT/OBSERVER)},'commands':argv,'host_profile':base['host']['profile'],'artifacts':artifacts(out),'observations':{'exit_code':run.returncode,'rows':rows}}
    path=out/'manifest.json';path.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
    if audit_default_producer(path):raise ValueError('default producer audit failed')
    return path

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True);a=sub.add_parser('prepare');a.add_argument('--base-manifest',type=Path,default=ROOT/'.cache/p09a2-producer/manifest.json');a.add_argument('--output',type=Path,default=ROOT/'.cache/p09a2c-producer');a=sub.add_parser('replay');a.add_argument('--manifest',type=Path,default=ROOT/'.cache/p09a2c-producer/manifest.json');args=p.parse_args()
    try:
        if args.action=='prepare':prepare(args.base_manifest,args.output)
        elif audit_default_producer(args.manifest):raise ValueError('default replay failed')
        print('Authenticated default-link producer observations passed; no Runtime/GPU execution claim');return 0
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):print('Default producer failed; local diagnostics retained');return 1
if __name__=='__main__':raise SystemExit(main())
