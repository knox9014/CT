"""Execute bounded lanes and bind results to exact source/config/tool identities."""
import argparse
import ctypes as c
import hashlib
import json
import importlib
import os
from pathlib import Path
import platform
import subprocess
import sys
from compatibility_registry import (RegistryContext, canonical_hash, validate_configuration,
    validate_coverage, validate_environment, validate_report, validate_toolchain)


def execute(command, *, cwd, log, timeout_s, env=None):
    try:
        with log.open('wb') as output:
            completed=subprocess.run(command,cwd=cwd,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=timeout_s)
        return dict(status='pass',reason='passed') if completed.returncode==0 else dict(status='fail',reason='test_failed')
    except subprocess.TimeoutExpired:return dict(status='fail',reason='tool_timeout')
    except OSError:return dict(status='fail',reason='tool_unavailable')


def corpus_outcome(child, *, case_id, expected_class, expected_hash):
    try:
        if not isinstance(child,list) or len(child)!=1 or child[0]['case_id']!=case_id:
            raise ValueError('wrong child case')
        observed=child[0]
        if observed['status']=='pass' and (observed['feature_supported']!=(expected_class=='supported')
                or observed.get('input_sha256')!=expected_hash):
            raise ValueError('wrong child classification or input')
        return {k:observed[k] for k in ('status','reason')}
    except (ValueError,KeyError,TypeError):return dict(status='fail',reason='test_failed')


def git(root,*args):
    return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL)


def source_fingerprint(root):
    paths=git(root,'ls-files','--cached','--others','--exclude-standard','-z').decode().split('\0')
    inputs={}
    for name in sorted(set(paths)):
        if name in ('Cargo.toml','Cargo.lock') or name.startswith(('crates/','tools/','scripts/','tests/',
                'include/','docs/compatibility/','.github/workflows/')):
            path=root/name
            if not path.resolve().is_relative_to(root.resolve()):raise ValueError('source escape')
            inputs[name]=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return canonical_hash(inputs)


RUNTIME_EVIDENCE={
    'arc.runtime':('p09a_runtime_check','audit_manifest','native','p09a-native-latest.json','p09a-build'),
    'arc.runtime_abi':('runtime_abi_evidence','audit','abi','p09a-abi-latest.json','p09a-build'),
    'arc.runtime_kernel_abi':('runtime_kernel_abi_evidence','audit','kernel-abi','p09a2-abi-latest.json','p09a2-build'),
    'arc.runtime_kernel':('p09a2_kernel_check','audit_manifest','kernel-native','p09a2-kernel-latest.json','p09a2-kernel'),
    'arc.runtime_default_abi':('runtime_default_abi_evidence','audit','default-abi','p09a2c-abi-latest.json','p09a2c-build'),
    'arc.runtime_default':('p09a2c_default_check','audit_manifest','default-native','p09a2c-default-latest.json','p09a2c-kernel'),
}


def clear_runtime_evidence(root,case_id):
    (root/'.cache'/RUNTIME_EVIDENCE[case_id][3]).unlink(missing_ok=True)


def execution_environment(root,case_id):
    env=os.environ.copy()
    env['CARGO_INCREMENTAL']='0'
    if case_id=='combined.all':
        for key,mode in [('CT_NVCC_COMPRESSED','compressed'),('CT_NVCC_PLAIN','plain')]:
            env[key]=str(root/'.cache/p09a2-producer'/('keep-'+mode)/'vector.fatbin')
    return env


def producer_evidence(directory,root,*,capture=False):
    from prepare_nvcc_probe import audit_probe,digest
    try:
        origin='.cache/p09a2-producer/manifest.json';target=root/origin;saved=directory/'nvcc-producer-evidence.json'
        expected=dict(origin=origin,sha256=digest(target),manifest=json.loads(target.read_bytes()))
        if capture:saved.write_text(json.dumps(expected,indent=2),encoding='utf-8')
        if json.loads(saved.read_bytes())!=expected:return ['producer evidence changed']
        return audit_probe(target)
    except (OSError,ValueError,TypeError,KeyError):return ['producer evidence unavailable']


def default_producer_evidence(directory,root,*,capture=False):
    from prepare_nvcc_default import audit_default_producer,digest
    try:
        origin='.cache/p09a2c-producer/manifest.json';target=root/origin;saved=directory/'nvcc-default-producer-evidence.json'
        expected=dict(origin=origin,sha256=digest(target),manifest=json.loads(target.read_bytes()))
        if capture:saved.write_text(json.dumps(expected,indent=2),encoding='utf-8')
        if json.loads(saved.read_bytes())!=expected:return ['default producer evidence changed']
        return audit_default_producer(target,root,execute=capture)
    except (OSError,ValueError,TypeError,KeyError):return ['default producer evidence unavailable']


def runtime_evidence(directory, root, case_id, *, capture=False):
    """Audit actual native artifacts; a child exit code/JSON cannot declare success."""
    try:
        if str(root/'tests') not in sys.path:sys.path.insert(0,str(root/'tests'))
        module,function,label,pointer_name,allowed=RUNTIME_EVIDENCE[case_id]
        audit=getattr(importlib.import_module(module),function)
        saved=directory/('runtime-'+label+'-manifest.json')
        if capture:
            pointer=json.loads((root/'.cache'/pointer_name).read_text())
            if set(pointer)!={'manifest'}:return ['invalid Runtime evidence pointer']
            target=(root/pointer['manifest']).resolve()
            if not target.is_relative_to(root/'.cache'/allowed):return ['Runtime evidence escape']
            saved.write_bytes(target.read_bytes())
        return audit(saved,root,execute=capture)
    except (OSError,ValueError,KeyError,TypeError):return ['Runtime native evidence unavailable']


def environment(native=False):
    env=dict(schema_version=1,os=platform.system()+' '+platform.version(),host_abi=platform.machine(),
        gpu_model=None,driver_version=None,runtime_versions={},compiler_versions={'python':platform.python_version()})
    rust=subprocess.run(['rustc','--version'],capture_output=True,timeout=10)
    if rust.returncode==0:env['compiler_versions']['rust']=rust.stdout.decode().strip()
    if os.name=='nt':
        try:
            locator=Path(os.environ.get('ProgramFiles(x86)',''))/'Microsoft Visual Studio/Installer/vswhere.exe'
            found=subprocess.run([str(locator),'-latest','-products','*','-requires',
                'Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],
                capture_output=True,timeout=10)
            if found.returncode==0 and found.stdout.strip():
                installed=Path(found.stdout.decode().strip())
                env['compiler_versions']['msvc']=(installed/'VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt').read_text().strip()
        except (OSError,UnicodeError,subprocess.SubprocessError):pass
    if native and os.name=='nt':
        class Driver(c.Structure):
            _fields_=[('stype',c.c_uint32),('next',c.c_void_p),('uuid',c.c_ubyte*16),('version',c.c_uint32)]
        class Device(c.Structure):
            _fields_=[('stype',c.c_uint32),('next',c.c_void_p),('kind',c.c_uint32),('vendor',c.c_uint32),
                ('device',c.c_uint32),('flags',c.c_uint32),('subdevice',c.c_uint32),('clock',c.c_uint32),
                ('max_alloc',c.c_uint64),('contexts',c.c_uint32),('priority',c.c_uint32),('threads',c.c_uint32),
                ('simd',c.c_uint32),('eus',c.c_uint32),('subslices',c.c_uint32),('slices',c.c_uint32),
                ('timer',c.c_uint64),('timestamp_bits',c.c_uint32),('kernel_bits',c.c_uint32),
                ('uuid',c.c_ubyte*16),('name',c.c_char*256)]
        try:
            loader=c.WinDLL('ze_loader.dll',winmode=0x800)
            p=c.c_void_p; u=c.c_uint32
            for name,args in {'zeInit':[u],'zeDriverGet':[c.POINTER(u),c.POINTER(p)],
                'zeDriverGetProperties':[p,c.POINTER(Driver)],'zeDriverGetApiVersion':[p,c.POINTER(u)],
                'zeDeviceGet':[p,c.POINTER(u),c.POINTER(p)],'zeDeviceGetProperties':[p,c.POINTER(Device)]}.items():
                getattr(loader,name).argtypes=args
                getattr(loader,name).restype=u
            if loader.zeInit(1):return env
            count=u()
            if loader.zeDriverGet(c.byref(count),None) or count.value>64:return env
            drivers=(p*count.value)()
            if loader.zeDriverGet(c.byref(count),drivers):return env
            for handle in drivers:
                n=u()
                if loader.zeDeviceGet(handle,c.byref(n),None) or n.value>64:continue
                devices=(p*n.value)()
                if loader.zeDeviceGet(handle,c.byref(n),devices):continue
                for device in devices:
                    props=Device();props.stype=3
                    if loader.zeDeviceGetProperties(device,c.byref(props)):continue
                    name=props.name.decode('utf-8',errors='replace')
                    if props.vendor!=0x8086 or 'B390' not in name:continue
                    driver=Driver();driver.stype=1;version=u()
                    if loader.zeDriverGetProperties(handle,c.byref(driver)) or loader.zeDriverGetApiVersion(handle,c.byref(version)):continue
                    env.update(gpu_model=name,driver_version=str(driver.version))
                    env['runtime_versions']['level-zero-api']=str(version.value)
                    return env
        except OSError:pass
    return env


def steps(lane, validator, lock):
    py=sys.executable
    cpu=[('cpu.fmt','semantic',['cargo','fmt','--check']),
        ('cpu.clippy','semantic',['cargo','clippy','--workspace','--all-targets','--','-D','warnings']),
        ('cpu.rust','semantic',['cargo','test','--workspace']),
        ('cpu.python','semantic',[py,'-m','unittest','discover','-s','tests','-p','test_*.py']),
        ('cpu.registry','semantic',[py,'scripts/check_coverage.py']),
        ('cpu.profile','semantic',[py,'scripts/check_compatibility_profile.py']),
        ('cpu.publication','semantic',[py,'scripts/check_public_artifacts.py','--tracked'])]
    cpu += [('cpu.runtime_fmt','semantic',['cargo','fmt','--manifest-path','crates/ct-cudart/Cargo.toml','--check']),
        ('cpu.runtime_clippy','semantic',['cargo','clippy','--manifest-path','crates/ct-cudart/Cargo.toml','--locked','--all-targets','--','-D','warnings']),
        ('cpu.runtime_rust','semantic',['cargo','test','--manifest-path','crates/ct-cudart/Cargo.toml','--locked']),
        ('cpu.runtime_profile','semantic',[py,'scripts/check_runtime_profile.py'])]
    validator_steps=[('validator.build','semantic',['cargo','build','-p','ct-codegen-spirv','--example','translate_module']),
        ('validator.real','validator',[py,'scripts/check_spirv_outputs.py','--tool',str(validator),'--lock',str(lock)])]
    producer=[('producer.build','semantic',['cargo','build','-p','ct-codegen-spirv','--example','translate_module'])]
    # producer.capture is a preparation command, never a required execution pass.
    corpus=json.loads((Path(__file__).resolve().parents[1]/'docs/compatibility/producer-corpus-v1.json').read_text())
    for item in corpus['cases']:
        producer.append(('producer.'+item['id'],'semantic',[py,'scripts/run_compiler_corpus.py','replay',
            '--case',item['id'],'--lock',str(lock),'--validator',str(validator),
            '--output','results/local/producer-'+item['id']+'.json']))
    producer.append(('producer.nvcc_fatbin','semantic',[py,'scripts/prepare_nvcc_probe.py','replay','--manifest','.cache/p09a2-producer/manifest.json','--rust']))
    producer.append(('producer.default_device_runtime','semantic',[py,'scripts/prepare_nvcc_default.py','replay','--manifest','.cache/p09a2c-producer/manifest.json']))
    arc=[('arc.build','semantic',['cargo','build','-p','ct-cuda']),
        ('arc.levelzero.abi','abi',['pwsh','-NoProfile','-File','scripts/check_level_zero_abi.ps1']),
        ('arc.cuda.abi','abi',['pwsh','-NoProfile','-File','scripts/check_cuda_abi.ps1','-Lock',str(lock)]),
        ('arc.native','native',['cargo','test','-p','ct-intel-smoke','--test','gpu','--','--ignored','--exact','arc_b390_executes_spirv_vector_add'])]
    # Catalog markers: arc.m3k_memory arc.m3l_arithmetic arc.m3m_predicates
    # arc.m3n_minmax arc.m3o_immediates
    for name in ('m3k_memory','m3l_arithmetic','m3m_predicates','m3n_minmax','m3o_immediates'):
        arc.append(('arc.'+name,'native',[py,'tests/'+name+'_check.py']))
    arc.append(('arc.consumers','behavior',['pwsh','-NoProfile','-File','scripts/run_m3_smoke.ps1']))
    # Catalog marker: arc.primary
    arc.append(('arc.primary','native',['pwsh','-NoProfile','-File','scripts/run_p05a_smoke.ps1']))
    # Catalog marker: arc.reset
    arc.append(('arc.reset','native',['pwsh','-NoProfile','-File','scripts/run_p05b_smoke.ps1']))
    # Catalog marker: arc.libraries
    arc.append(('arc.libraries','native',['pwsh','-NoProfile','-File','scripts/run_p05c_smoke.ps1']))
    # Catalog marker: arc.context_destroy
    arc.append(('arc.context_destroy','native',['pwsh','-NoProfile','-File','scripts/run_p05d_smoke.ps1']))
    # Catalog marker: arc.device_memory
    arc.append(('arc.device_memory','native',['pwsh','-NoProfile','-File','scripts/run_p06a_smoke.ps1']))
    # Catalog marker: arc.memory_queries
    arc.append(('arc.memory_queries','native',['pwsh','-NoProfile','-File','scripts/run_p06q_smoke.ps1']))
    arc.append(('arc.runtime_abi','abi',['pwsh','-NoProfile','-File','scripts/check_runtime_abi.ps1']))
    arc.append(('arc.runtime','native',['pwsh','-NoProfile','-File','scripts/run_p09a_smoke.ps1']))
    arc.append(('arc.runtime_kernel_abi','abi',['pwsh','-NoProfile','-File','scripts/check_runtime_kernel_abi.ps1']))
    arc.append(('arc.runtime_kernel','native',['pwsh','-NoProfile','-File','scripts/run_p09a2_smoke.ps1','-HostProfile','diagnostic']))
    arc.append(('arc.runtime_default_abi','abi',['pwsh','-NoProfile','-File','scripts/check_runtime_default_abi.ps1']))
    arc.append(('arc.runtime_default','native',['pwsh','-NoProfile','-File','scripts/run_p09a2c_smoke.ps1','-HostProfile','diagnostic']))
    combined=cpu+validator_steps+producer+arc+[
        ('combined.all','semantic',['cargo','test','--workspace','--','--include-ignored'])]
    return {'cpu':cpu,'validator':validator_steps,'producer':producer,'arc':arc,'combined':combined}[lane]


def configuration(root, lane, selected):
    corpus=json.loads((root/'docs/compatibility/producer-corpus-v1.json').read_text())
    config=dict(schema_version=1,lane=lane,cases=[])
    for name,kind,command in selected:
        corpus_case=next((x for x in corpus['cases'] if name=='producer.'+x['id']),None)
        test_id='scripts/run_compiler_corpus.py#run_case' if corpus_case else 'scripts/run_validation.py#'+name
        artifacts={'producer_ptx':corpus_case['output_sha256']} if corpus_case else {}
        parameters={'command_id':name,'timeout_s':300,**({'expected_class':corpus_case['expected_class']} if corpus_case else {})}
        if name.startswith(('arc.m3k_','arc.m3l_','arc.m3m_','arc.m3n_','arc.m3o_')):
            milestone=name.split('.')[1].split('_')[0]
            for role,path in {'baseline_dll':root/'.cache'/(milestone+'-baseline')/'ct_cuda.dll',
                'baseline_hash_record':root/'.cache'/(milestone+'-baseline')/'sha256.txt',
                'nvfatbin_package':root/'.cache/reference/nvidia_nvfatbin_cu12-12.4.99-py3-none-win_amd64.whl'}.items():
                artifacts[role]=hashlib.sha256(path.read_bytes()).hexdigest()
            parameters['baseline_provenance']='preserved_local_binary_source_revision_unverified'
        if name=='combined.all':
            for variant in ('plain','compressed'):
                artifacts[variant+'_fatbin']=hashlib.sha256((root/'.cache/reference/m3e'/(variant+'.fatbin')).read_bytes()).hexdigest()
        nvcc_tools=['cuda-nvcc-producer','cuda-cudart-producer','cuda-cccl-producer','ms-stl-diagnostic']
        if name in ('producer.nvcc_fatbin','arc.runtime_kernel_abi','arc.runtime_kernel','combined.all'):
            parameters['producer_host_profile']='diagnostic'
            for role,path in {'nvcc_producer_manifest':'.cache/p09a2-producer/manifest.json',
                'nvcc_compressed_fatbin':'.cache/p09a2-producer/keep-compressed/vector.fatbin',
                'nvcc_plain_fatbin':'.cache/p09a2-producer/keep-plain/vector.fatbin',
                'nvcc_fixture':'tests/fixtures/p09a2/vector.cu','runtime_profile':'docs/compatibility/runtime-profile-v1.json'}.items():
                artifacts[role]=hashlib.sha256((root/path).read_bytes()).hexdigest()
        if name=='arc.runtime_kernel_abi':
            from runtime_kernel_abi_evidence import INPUTS
            for index,path in enumerate(INPUTS):artifacts['kernel_abi_input_'+str(index)]=hashlib.sha256((root/path).read_bytes()).hexdigest()
        if name=='arc.runtime_kernel':
            if str(root/'tests') not in sys.path:sys.path.insert(0,str(root/'tests'))
            from p09a2_kernel_check import INPUTS
            for index,path in enumerate(INPUTS):artifacts['kernel_input_'+str(index)]=hashlib.sha256((root/path).read_bytes()).hexdigest()
        if name in ('producer.default_device_runtime','arc.runtime_default_abi','arc.runtime_default'):
            parameters['producer_host_profile']='diagnostic'
            for role,path in {'default_producer_manifest':'.cache/p09a2c-producer/manifest.json','default_producer_source':'tests/fixtures/p09a2/vector.cu','default_observer':'tests/p09a2c_registration_observer.cpp','default_recipe':'scripts/prepare_nvcc_default.py','runtime_profile':'docs/compatibility/runtime-profile-v1.json'}.items():
                artifacts[role]=hashlib.sha256((root/path).read_bytes()).hexdigest()
            if name=='arc.runtime_default_abi':
                from runtime_default_abi_evidence import INPUTS
                for index,path in enumerate(INPUTS):artifacts['default_abi_input_'+str(index)]=hashlib.sha256((root/path).read_bytes()).hexdigest()
            if name=='arc.runtime_default':
                if str(root/'tests') not in sys.path:sys.path.insert(0,str(root/'tests'))
                from p09a2c_default_check import INPUTS
                for index,path in enumerate(INPUTS):artifacts['default_input_'+str(index)]=hashlib.sha256((root/path).read_bytes()).hexdigest()
        if name in ('arc.runtime_abi','arc.runtime'):
            for role,path in {'runtime_profile':'docs/compatibility/runtime-profile-v1.json',
                'runtime_abi':'tests/runtime_reference_abi.cpp','declared_abi':'tests/runtime_declared_abi.cpp',
                'runtime_consumer':'tests/p09a_runtime_app.c','runtime_exports':'tests/p09a_runtime.def',
                'fake_provider':'tests/p09a_fake_driver.c','noop_provider':'tests/p09a_noop_driver.c',
                'control_exports':'tests/p09a_driver_control.def'}.items():
                artifacts[role]=hashlib.sha256((root/path).read_bytes()).hexdigest()
        config['cases'].append(dict(case_id=name,test_id=test_id,execution_kind=kind,application_id=None,
            parameters=parameters,artifact_requirements=artifacts,
            tool_ids=nvcc_tools if name in ('producer.nvcc_fatbin','arc.runtime_kernel_abi','arc.runtime_kernel','combined.all','producer.default_device_runtime','arc.runtime_default_abi','arc.runtime_default') else ['cuda-runtime-headers','cuda-nvcc-support-headers'] if name in ('arc.runtime_abi','arc.runtime') else ['spirv-val'] if kind=='validator' or (corpus_case and corpus_case['expected_class']=='supported') else ['cuda-headers'] if name in ('arc.cuda.abi','arc.device_memory','arc.memory_queries') else []))
    return config


def validate_lane_bundle(directory, root, lane, *, expected_commit, expected_tree, expected_clean,
                         expected_toolchain=None):
    """Reconstruct expectations independently of the serialized runner report."""
    try:
        read=lambda n:json.loads((directory/n).read_text())
        report,env,config,lock,source=(read(n) for n in ('report.json','environment.json',
            'configuration.json','toolchain-lock.json','source.json'))
        coverage=json.loads((root/'docs/compatibility/coverage-v1.json').read_text())
        approved_lock=expected_toolchain if expected_toolchain is not None else json.loads(
            (root/'docs/compatibility/toolchain-lock-v1.json').read_text())
        catalog={x['id']:x for x in coverage['test_catalog']}
        errors=validate_environment(env)+validate_toolchain(lock)+validate_configuration(config,test_catalog=catalog)
        if validate_toolchain(approved_lock) or canonical_hash(lock)!=canonical_hash(approved_lock):
            errors.append('bundle toolchain differs from independent execution lock')
        expected=configuration(root,lane,steps(lane,Path('validator'),Path('lock')))
        if config!=expected:errors.append('configuration differs from approved lane')
        if source.get('source_commit')!=expected_commit or source.get('source_tree_sha256')!=expected_tree or source.get('clean')!=expected_clean:
            errors.append('bundle source identity mismatch')
        if source.get('release_claim') is not False:errors.append('bundle cannot claim release')
        context=RegistryContext(expected_commit,'arc-preview-foundation',canonical_hash(env),canonical_hash(approved_lock),
            canonical_hash(coverage['test_catalog']),canonical_hash(expected),catalog,
            {x['case_id']:x for x in expected['cases']},{},{t['id']:t for t in approved_lock['tools']},
            frozenset(x['case_id'] for x in expected['cases']),lane)
        errors+=validate_report(report,context=context)
        for case in report['cases']:
            if case['case_id'] in RUNTIME_EVIDENCE and case['status']=='pass':
                errors+=runtime_evidence(directory,root,case['case_id'])
            if case['case_id']=='producer.nvcc_fatbin' and case['status']=='pass':errors+=producer_evidence(directory,root)
            if case['case_id']=='producer.default_device_runtime' and case['status']=='pass':errors+=default_producer_evidence(directory,root)
        return errors,report
    except (OSError,ValueError,KeyError,TypeError):return ['lane bundle unavailable or malformed'],None


def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lane',choices=('cpu','validator','producer','arc','combined'),required=True)
    parser.add_argument('--required',action='store_true')
    parser.add_argument('--output-directory',type=Path,required=True)
    parser.add_argument('--validator',type=Path,default=root/'.cache/universal-foundation/spirv-build/tools/Release/spirv-val.exe')
    parser.add_argument('--lock',type=Path,default=root/'docs/compatibility/toolchain-lock-v1.json')
    args=parser.parse_args()
    try:
        output=args.output_directory.resolve()
        if not output.is_relative_to(root/'results/local'):raise ValueError('output must remain local')
        output.mkdir(parents=True,exist_ok=True)
        folder=root/'docs/compatibility'
        coverage=json.loads((folder/'coverage-v1.json').read_text())
        tools=json.loads(args.lock.read_text())
        if validate_coverage(coverage,root) or validate_toolchain(tools):raise ValueError('invalid registries')
        baseline=git(root,'rev-parse','HEAD').decode().strip()
        fingerprint=source_fingerprint(root)
        clean=not bool(git(root,'status','--porcelain','--untracked-files=all'))
        actual_env=environment(args.lane in ('arc','combined'))
        if validate_environment(actual_env):raise ValueError('invalid environment')
        selected=steps(args.lane,args.validator.resolve(),args.lock.resolve())
        catalog={t['id']:t for t in coverage['test_catalog']}
        config=configuration(root,args.lane,selected)
        if validate_configuration(config,test_catalog=catalog):raise ValueError('invalid configuration')
        reports=[];stopped=False
        for case,(_,_,command) in zip(config['cases'],selected):
            if stopped:result=dict(status='not_run',reason='not_run')
            elif case['case_id'].startswith('arc.') and case['execution_kind'] in ('native','behavior') and actual_env['gpu_model'] is None:
                result=dict(status='fail' if args.required else 'skipped',reason='hardware_unavailable')
            elif case['execution_kind']=='validator' and not args.validator.is_file():
                result=dict(status='fail' if args.required else 'skipped',reason='tool_unavailable')
            else:
                print('Running '+case['case_id'],flush=True)
                if case['case_id'] in RUNTIME_EVIDENCE:clear_runtime_evidence(root,case['case_id'])
                result=execute(command,cwd=root,log=output/(case['case_id']+'.log'),timeout_s=300,env=execution_environment(root,case['case_id']))
                if case['case_id'] in RUNTIME_EVIDENCE and result['status']=='pass':
                    if runtime_evidence(output,root,case['case_id'],capture=True):result=dict(status='fail',reason='test_failed')
                if case['case_id']=='producer.nvcc_fatbin' and result['status']=='pass':
                    if producer_evidence(output,root,capture=True):result=dict(status='fail',reason='test_failed')
                if case['case_id']=='producer.default_device_runtime' and result['status']=='pass':
                    if default_producer_evidence(output,root,capture=True):result=dict(status='fail',reason='test_failed')
                stopped=result['reason']=='tool_timeout'
                if case['case_id'].startswith('producer.') and case['case_id'] not in ('producer.build','producer.nvcc_fatbin','producer.default_device_runtime'):
                    # Preserve child outcome; capture_only/not_run can never be
                    # converted to pass by a successful wrapper exit code.
                    try:
                        child=json.loads((output/(case['case_id']+'.log')).read_text())['cases']
                        if result['status']=='pass':
                            result=corpus_outcome(child,case_id=case['case_id'].removeprefix('producer.'),
                                expected_class=case['parameters']['expected_class'],
                                expected_hash=case['artifact_requirements']['producer_ptx'])
                    except (OSError,ValueError,KeyError):
                        result=dict(status='fail',reason='test_failed')
                if case['case_id']=='arc.native' and result['status']=='pass' and b'test arc_b390_executes_spirv_vector_add ... ok' not in (output/(case['case_id']+'.log')).read_bytes():
                    result=dict(status='fail',reason='test_failed')
            reports.append(dict(case_id=case['case_id'],test_id=case['test_id'],execution_kind=case['execution_kind'],
                application_id=None,artifact_hashes=case['artifact_requirements'] if result['status']=='pass' else {},tool_ids=case['tool_ids'],**result))
        report=dict(schema_version=1,source_commit=baseline,target_profile='arc-preview-foundation',lane=args.lane,
            environment_id=canonical_hash(actual_env),toolchain_lock_sha256=canonical_hash(tools),
            test_catalog_sha256=canonical_hash(coverage['test_catalog']),configuration_sha256=canonical_hash(config),cases=reports)
        context=RegistryContext(baseline,report['target_profile'],report['environment_id'],canonical_hash(tools),
            report['test_catalog_sha256'],canonical_hash(config),catalog,{x['case_id']:x for x in config['cases']},{},
            {t['id']:t for t in tools['tools']},frozenset(x['case_id'] for x in config['cases']) if args.required else frozenset(),args.lane)
        errors=validate_report(report,context=context)
        if baseline!=git(root,'rev-parse','HEAD').decode().strip() or fingerprint!=source_fingerprint(root):
            errors.append('source changed during execution')
        if config!=configuration(root,args.lane,selected):
            errors.append('execution input artifacts changed during execution')
        for filename,data in [('environment.json',actual_env),('configuration.json',config),('toolchain-lock.json',tools),
                ('report.json',report),('source.json',dict(source_commit=baseline,source_tree_sha256=fingerprint,clean=clean,
                release_claim=False,unexecuted_hardware=['NVIDIA','AMD']))]:
            (output/filename).write_text(json.dumps(data,indent=2)+'\n')
        print(json.dumps(dict(lane=args.lane,source_commit=baseline,source_tree_sha256=fingerprint,
            clean=clean,release_claim=False,cases=[dict(case_id=r['case_id'],status=r['status']) for r in reports],errors=errors)))
        return int(bool(errors) or any(r['status']=='fail' for r in reports))
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):
        print(json.dumps(dict(status='fail',reason='validation_inputs_unavailable')));return 1


if __name__=='__main__':raise SystemExit(main())
