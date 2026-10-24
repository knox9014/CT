"""Capture original-header global ABI probes and Runtime registration ABI."""
import json,os,shutil,subprocess,uuid
from pathlib import Path
from prepare_nvcc_probe import digest
from run_validation import source_fingerprint
from p04a_abi_evidence import INPUTS,NAMES,audit,abi_commands
from prepare_nvcc_default import host_environment
ROOT=Path(__file__).resolve().parents[1]
def main():
 pointer=ROOT/'.cache/p04a-abi-latest.json';pointer.unlink(missing_ok=True)
 folder=ROOT/'.cache/p04a-abi'/uuid.uuid4().hex;folder.mkdir(parents=True)
 producer=ROOT/'.cache/p09a2-producer/manifest.json'
 base,env=host_environment(producer,folder)
 env['CARGO_INCREMENTAL']='0';env['CARGO_TARGET_DIR']=str(folder/'target')
 commands=abi_commands(folder,producer,base)
 for i,argv in enumerate(commands):
  r=subprocess.run(argv,cwd=ROOT,env=env,capture_output=True,timeout=600);(folder/('build-'+str(i)+'.log')).write_bytes(r.stdout+r.stderr)
  if r.returncode:raise ValueError('ABI build failed')
 shutil.copyfile(folder/'target/debug/ct_cuda.dll',folder/'ct_cuda.dll')
 for name in NAMES[1:]:shutil.copyfile(ROOT/'.cache/universal-foundation/abi'/name,folder/name)
 p=json.loads((ROOT/'.cache/p09a2c-abi-latest.json').read_bytes());shutil.copyfile(ROOT/p['manifest'],folder/'runtime-abi-manifest.json')
 def item(p):return dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p))
 lock=json.loads((ROOT/'docs/compatibility/toolchain-lock-v1.json').read_bytes());tool=next(t for t in lock['tools'] if t['id']=='cuda-headers')
 m=dict(schema_version=1,case_id='arc.global_abi',producer=item(producer),compiler={**base['host']['tools'],'vcvars':base['host']['vcvars']},commands=commands,source_tree=source_fingerprint(ROOT),inputs={n:digest(ROOT/n) for n in INPUTS},headers={n:item(ROOT/'.cache/reference/cuda-12.0/include'/n) for n in tool['files']},artifacts={n:item(folder/n) for n in NAMES},observations={},runtime_abi=item(folder/'runtime-abi-manifest.json'))
 for label,exe in [('reference','cuda_reference_abi.exe'),('declared','cuda_declared_abi.exe'),('consumer','cuda_reference_consumer.exe')]:
  r=subprocess.run([str(folder/exe)]+([str(folder/'ct_cuda.dll')] if label=='consumer' else []),cwd=folder,capture_output=True,timeout=30)
  out=folder/(label+'.stdout');err=folder/(label+'.stderr');out.write_bytes(r.stdout);err.write_bytes(r.stderr)
  m['observations'][label]=dict(exit_code=r.returncode,stdout=item(out),stderr=item(err))
 path=folder/'abi-manifest.json';path.write_text(json.dumps(m,indent=2),encoding='utf-8')
 if audit(path,ROOT,execute=True):raise ValueError('ABI reconstruction failed')
 pointer.write_text(json.dumps(dict(manifest=path.relative_to(ROOT).as_posix())),encoding='utf-8')
 print('Global original-header ABI and independent replay passed')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,KeyError,subprocess.SubprocessError):print('Global ABI failed; local diagnostics retained');raise SystemExit(1)
