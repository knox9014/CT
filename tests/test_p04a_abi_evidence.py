"""Synthetic ABI closure tests; mocks never count as native ABI proof."""
import copy,json,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from p04a_abi_evidence import audit,INPUTS,NAMES,GLOBAL,CONSUMER,abi_commands
from prepare_nvcc_probe import digest
class AbiClosureTests(unittest.TestCase):
 def setUp(self):
  cache=ROOT/'.cache/p04a-abi';cache.mkdir(exist_ok=True,parents=True)
  self.tmp=tempfile.TemporaryDirectory(dir=cache);self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'root';self.folder=self.root/'.cache/p04a-abi/candidate';self.folder.mkdir(parents=True)
  for name in INPUTS:
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
  self.item=lambda p:dict(path=p.relative_to(self.root).as_posix(),sha256=digest(p))
  lock=json.loads((self.root/'docs/compatibility/toolchain-lock-v1.json').read_bytes());tool=next(t for t in lock['tools'] if t['id']=='cuda-headers');headers={}
  for name in tool['files']:
   p=self.root/'.cache/reference/cuda-12.0/include'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(name.encode());headers[name]=self.item(p)
  for name in NAMES:(self.folder/name).write_bytes(name.encode())
  target=self.folder/'target/debug/ct_cuda.dll';target.parent.mkdir(parents=True);shutil.copyfile(self.folder/'ct_cuda.dll',target)
  observations={};data=b'\n'.join([GLOBAL]+[('cu_other_'+str(i)).encode() for i in range(38)])+b'\n'
  for label in ('reference','declared','consumer'):
   out=self.folder/(label+'.stdout');err=self.folder/(label+'.stderr');out.write_bytes(CONSUMER if label=='consumer' else data);err.write_bytes(b'');observations[label]=dict(exit_code=0,stdout=self.item(out),stderr=self.item(err))
  p=self.folder/'runtime-abi-manifest.json';p.write_text('{}')
  producer=self.root/'.cache/p09a2-producer/manifest.json';producer.parent.mkdir(parents=True)
  base=dict(host=dict(profile='diagnostic',tools={'cl.exe':{'path':str(self.root/'compiler/cl.exe'),'sha256':'b'*64}},vcvars={'path':str(self.root/'compiler/vcvars64.bat'),'sha256':'c'*64}))
  producer.write_text(json.dumps(base))
  self.good=dict(producer=self.item(producer),compiler={**base['host']['tools'],'vcvars':base['host']['vcvars']},commands=abi_commands(self.folder,producer,base,self.root),schema_version=1,case_id='arc.global_abi',source_tree='a'*64,inputs={n:digest(self.root/n) for n in INPUTS},headers=headers,artifacts={n:self.item(self.folder/n) for n in NAMES},observations=observations,runtime_abi=self.item(p))
  for name,value in [('p04a_abi_evidence.source_fingerprint','a'*64),('p04a_abi_evidence.validate_tool_execution',[]),('p04a_abi_evidence.runtime_audit',[]),('p04a_abi_evidence.audit_probe',[])]:
   mock=patch(name,return_value=value);mock.start();self.addCleanup(mock.stop)
  self.path=self.folder/'abi-manifest.json';self.save(self.good)
 def save(self,m):self.path.write_text(json.dumps(m))
 def test_rehashed_compatible_foreign_dll_is_not_candidate_output(self):
  self.assertEqual(audit(self.path,self.root),[])
  m=copy.deepcopy(self.good);p=self.folder/'ct_cuda.dll';p.write_bytes(b'compatible but different DLL');m['artifacts']['ct_cuda.dll']=self.item(p);self.save(m)
  self.assertTrue(audit(self.path,self.root))
 def test_unbound_child_success_cannot_pass(self):
  self.save(dict(status='pass'));self.assertTrue(audit(self.path,self.root))

 def test_build_commands_and_compiler_are_not_self_declared(self):
  self.assertEqual(audit(self.path,self.root),[])
  for mutate in [lambda m:m['commands'][1].pop(),lambda m:m['compiler']['cl.exe'].update(sha256='d'*64),lambda m:m.pop('compiler')]:
   m=copy.deepcopy(self.good);mutate(m);self.save(m);self.assertTrue(audit(self.path,self.root))

 def test_runtime_abi_recipe_uses_repository_relative_producer(self):
  command=self.good['commands'][2]
  self.assertEqual(command[command.index('-ProducerManifest')+1],'.cache/p09a2-producer/manifest.json')
