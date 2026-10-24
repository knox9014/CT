"""Independent original-header Driver39 plus existing Runtime22 ABI evidence."""
import json,shutil,subprocess,tempfile
from pathlib import Path
from prepare_nvcc_probe import digest
from run_validation import source_fingerprint
from compatibility_registry import validate_toolchain,validate_tool_execution
from check_toolchain_files import observed_platform
from runtime_default_abi_evidence import audit as runtime_audit
ROOT=Path(__file__).resolve().parents[1]
INPUTS=['include/ct_cuda.h','tests/cuda_reference_abi.cpp','tests/cuda_declared_abi.cpp','tests/cuda_reference_consumer.cpp','tests/cuda_abi_probe.hpp','scripts/check_cuda_abi.ps1','scripts/run_p04a_abi.py','scripts/p04a_abi_evidence.py','docs/compatibility/toolchain-lock-v1.json']
NAMES=('ct_cuda.dll','cuda_reference_abi.exe','cuda_declared_abi.exe','cuda_reference_consumer.exe')
GLOBAL=b'cuModuleGetGlobal_v2:int:4:4(ptr[uint:8:8];ptr[uint:8:8];ptr[opaque];ptr[const-int:1:1];)'
CONSUMER=b'Official PFN consumer: error mapping, resolver ABI versions and primary calls passed.\n'
def local(root,name):
 p=(root/name).resolve()
 if not p.is_relative_to(root/'.cache/p04a-abi'):raise ValueError('ABI artifact escape')
 return p
def item(root,row):
 if set(row)!={'path','sha256'}:raise ValueError('ABI artifact schema')
 p=local(root,row['path'])
 if digest(p)!=row['sha256']:raise ValueError('ABI bytes changed')
 return p
def audit(path,root=ROOT,*,execute=False):
 try:
  m=json.loads(Path(path).read_bytes())
  if set(m)!={'schema_version','case_id','source_tree','inputs','headers','artifacts','observations','runtime_abi'} or type(m['schema_version']) is not int or m['schema_version']!=1 or m['case_id']!='arc.global_abi':return ['global ABI schema']
  if m['source_tree']!=source_fingerprint(root) or m['inputs']!={n:digest(root/n) for n in INPUTS}:return ['global ABI source']
  lock=json.loads((root/'docs/compatibility/toolchain-lock-v1.json').read_bytes())
  if validate_toolchain(lock):return ['global ABI lock']
  tool=next(t for t in lock['tools'] if t['id']=='cuda-headers')
  if set(m['headers'])!=set(tool['files']):return ['global ABI header set']
  observed={}
  for name,row in m['headers'].items():
   if set(row)!={'path','sha256'}:return ['global ABI header schema']
   p=(root/row['path']).resolve()
   if p!=root/'.cache/reference/cuda-12.0/include'/name or digest(p)!=row['sha256']:return ['global ABI header changed']
   observed[name]=row['sha256']
  if validate_tool_execution(tool,observed_platform=observed_platform(),observed_hashes=observed,required=True):return ['global ABI header pin']
  if set(m['artifacts'])!=set(NAMES) or set(m['observations'])!={'reference','declared','consumer'}:return ['global ABI roles']
  files={n:item(root,r) for n,r in m['artifacts'].items()};folder=files['ct_cuda.dll'].parent
  if any(p.parent!=folder or p.name!=n for n,p in files.items()):return ['global ABI artifact role paths']
  outputs={}
  for name,row in m['observations'].items():
   if set(row)!={'exit_code','stdout','stderr'} or type(row['exit_code']) is not int or row['exit_code']!=0:return ['global ABI observation']
   out=item(root,row['stdout']);err=item(root,row['stderr'])
   if out!=folder/(name+'.stdout') or err!=folder/(name+'.stderr') or err.read_bytes():return ['global ABI logs']
   outputs[name]=out.read_bytes().replace(b'\r\n',b'\n')
  if outputs['reference']!=outputs['declared'] or GLOBAL not in outputs['reference'].splitlines() or sum(line.startswith(b'cu') for line in outputs['reference'].splitlines())!=39 or outputs['consumer']!=CONSUMER:return ['global ABI normalized signatures']
  runtime=item(root,m['runtime_abi'])
  errors=runtime_audit(runtime,root,execute=execute)
  if errors:return errors
  if execute:
   with tempfile.TemporaryDirectory(dir=root/'.cache/p04a-abi') as d:
    work=Path(d)
    for name,p in files.items():shutil.copyfile(p,work/name)
    for label,exe in [('reference','cuda_reference_abi.exe'),('declared','cuda_declared_abi.exe'),('consumer','cuda_reference_consumer.exe')]:
     argv=[str(work/exe)]+([str(work/'ct_cuda.dll')] if label=='consumer' else [])
     r=subprocess.run(argv,cwd=work,capture_output=True,timeout=30)
     if r.returncode or r.stderr or r.stdout.replace(b'\r\n',b'\n')!=outputs[label]:return ['global ABI fresh replay']
   return audit(path,root,execute=False)
  return []
 except (OSError,ValueError,KeyError,TypeError,StopIteration,subprocess.SubprocessError):return ['global ABI evidence unavailable']
