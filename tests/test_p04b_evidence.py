"""Synthetic closure fixtures never count as native execution evidence."""
import copy,json,shutil,sys,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from p04b_evidence import audit_manifest,audit_abi
from run_p04b_smoke import SOURCES,ARTIFACTS,MODES,ORDERS,ABI_EXPECTED,compiler_commands,rust_commands,payload_roles,control_expected
from p04b_symbol_check import expected,expected_noop
from prepare_nvcc_probe import digest
class SymbolEvidenceTests(unittest.TestCase):
 def setUp(self):
  cache=ROOT/'.cache/p04b-smoke';cache.mkdir(parents=True,exist_ok=True)
  self.tmp=tempfile.TemporaryDirectory(dir=cache);self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)/'root';self.folder=self.root/'.cache/p04b-smoke/candidate';self.folder.mkdir(parents=True)
  for source in SOURCES:
   p=self.root/source;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/source,p)
  f=self.folder
  self.item=lambda p:dict(path=p.relative_to(self.root).as_posix(),sha256=digest(p))
  producer=self.root/'.cache/base/manifest.json';producer.parent.mkdir(parents=True)
  base={'host':{'profile':'diagnostic','tools':{'cl.exe':{'path':str(self.root/'compiler/cl.exe')}}}};producer.write_text(json.dumps(base))
  self.files={r:f/n for r,n in ARTIFACTS.items()}
  for r,p in self.files.items():p.write_bytes(r.encode())
  for target,name in [('driver-target','ct_cuda.dll'),('runtime-target','ct_cudart.dll')]:
   p=f/target/'debug'/name;p.parent.mkdir(parents=True);shutil.copyfile(f/name,p)
  shutil.copyfile(self.root/SOURCES[0],f/'symbol_runtime.cu')
  outputs={}
  for name in ('symbol_runtime.ptx','symbol_runtime.fatbin','symbol_runtime.cudafe1.stub.c','host_dlink.fatbin'):
   p=f/'keep-symbol_runtime'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('ct_counter ct_other ld.volatile.global st.volatile.global __cudaRegisterVar');outputs[p.relative_to(f).as_posix()]=digest(p)
  self.files['image']=f/'keep-symbol_runtime/symbol_runtime.fatbin'
  m=dict(schema_version=1,scope='diagnostic_p04b_symbols',release_claim=False,source_tree='a'*64,inputs={n:digest(self.root/n) for n in SOURCES},producer=self.item(producer),commands=compiler_commands(producer,f,base,self.root),rust_commands=rust_commands(f),artifacts={r:self.item(p) for r,p in self.files.items() if r!='image'},compiler_outputs=outputs,abi=[],runs=[])
  pure=f/'pure';pure.mkdir()
  for name,role in [('native.exe','native'),('cudart64_12.dll','runtime')]:shutil.copyfile(self.files[role],pure/name)
  for role in ('reference','declared','pure'):
   out=f/(role+'.stdout');err=f/(role+'.stderr');out.write_bytes(b'SYMBOL_NATIVE pure 26 13 21 801\n' if role=='pure' else ABI_EXPECTED);err.write_bytes(b'');m['abi'].append(dict(role=role,exit_code=0,stdout=self.item(out),stderr=self.item(err)))
  for i,mode in enumerate(MODES):
   seed=123+i;order=ORDERS.get(mode,0);out=f/(mode+'.stdout');err=f/(mode+'.stderr')
   value=(expected_noop if mode=='noop' else expected)(seed,order) if mode in ORDERS else None
   out.write_bytes(json.dumps(value).encode() if value else control_expected(mode));err.write_bytes(b'')
   bundle=f/('bundle-'+mode);bundle.mkdir();roles=payload_roles(mode)
   for name,role in roles.items():shutil.copyfile(self.files[role],bundle/name)
   m['runs'].append(dict(mode=mode,seed=seed,order=order,exit_code=0,stdout=self.item(out),stderr=self.item(err),bundle=bundle.relative_to(self.root).as_posix(),payloads={n:digest(self.files[r]) for n,r in roles.items()}))
  for name,value in [('p04b_evidence.source_fingerprint','a'*64),('p04b_evidence.audit_probe',[])]:
   p=patch(name,return_value=value);p.start();self.addCleanup(p.stop)
  p=patch('p04b_evidence.inspect_pe',return_value={'imports':[{'library':'cudart64_12.dll','symbols':['__cudaRegisterVar','__cudaRegisterFatBinary','__cudaRegisterFunction','cudaLaunchKernel','cudaGetSymbolAddress','cudaGetSymbolSize','cudaMemcpyToSymbol','cudaMemcpyFromSymbol']}]});p.start();self.addCleanup(p.stop)
  self.good=m;self.path=f/'manifest.json';self.save(m)
 def save(self,m):self.path.write_text(json.dumps(m),encoding='utf-8')
 def test_exact_fixture_and_schema_tampering(self):
  self.assertEqual(audit_manifest(self.path,self.root),[])
  for change in [lambda m:m.update(status='pass'),lambda m:m.update(source_tree='b'*64),lambda m:m['inputs'].update({SOURCES[0]:'c'*64}),lambda m:m['commands'][0]['argv'].append('--cudadevrt=none'),lambda m:m['runs'][0].update(exit_code=True),lambda m:m['runs'][0].update(order=True),lambda m:m['runs'].pop(),lambda m:m['runs'][2].update(seed=m['runs'][0]['seed']),lambda m:m['compiler_outputs'].pop('keep-symbol_runtime/host_dlink.fatbin'),lambda m:m['artifacts']['host'].update(path='../escape.exe')]:
   bad=copy.deepcopy(self.good);change(bad);self.save(bad);self.assertTrue(audit_manifest(self.path,self.root))
 def test_raw_files_and_bundles_are_bound(self):
  for relative in ('host.exe','ct_cudart.dll','reference.exe','keep-symbol_runtime/symbol_runtime.ptx','positive_symbol_first.stdout','pure/cudart64_12.dll','bundle-noop/nvcuda.dll'):
   p=self.folder/relative;raw=p.read_bytes();p.write_bytes(raw+b'changed');self.assertTrue(audit_manifest(self.path,self.root));p.write_bytes(raw)
  self.assertEqual(audit_manifest(self.path,self.root),[])
 def test_rehashed_dll_still_requires_cargo_output(self):
  m=copy.deepcopy(self.good);p=self.folder/'ct_cudart.dll';p.write_bytes(b'compatible foreign runtime');m['artifacts']['runtime']=self.item(p)
  self.save(m);self.assertTrue(audit_manifest(self.path,self.root))
 def test_forged_numerical_success_and_noop_corruption(self):
  for mode in ('positive_symbol_first','noop'):
   m=copy.deepcopy(self.good);p=self.folder/(mode+'.stdout');raw=p.read_bytes();value=json.loads(raw);value['contexts'][0]['runs'][0][0]^=1;p.write_text(json.dumps(value));next(r for r in m['runs'] if r['mode']==mode)['stdout']=self.item(p);self.save(m);self.assertTrue(audit_manifest(self.path,self.root));p.write_bytes(raw)
 def test_fresh_replay_isolated_and_cannot_use_child_exit_zero(self):
  with patch('p04b_evidence.subprocess.run',return_value=subprocess.CompletedProcess([],0,b'{}',b'')) as child:
   self.assertTrue(audit_manifest(self.path,self.root,execute=True));self.assertTrue(child.called)
   self.assertNotEqual(child.call_args.kwargs['cwd'],self.folder/'bundle-positive_symbol_first')
 def test_abi_and_native_gate_cannot_substitute_each_other(self):
  self.assertTrue(audit_abi(self.path,self.root))
  m=copy.deepcopy(self.good);m['scope']='diagnostic_p04b_symbol_abi';m['runs']=[];self.save(m)
  self.assertEqual(audit_abi(self.path,self.root),[]);self.assertTrue(audit_manifest(self.path,self.root))
