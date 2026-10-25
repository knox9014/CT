import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from runtime_default_abi_evidence import check_output,audit
class DefaultAbiEvidenceTests(unittest.TestCase):
 def test_exact_output_not_child_success(self):
  self.assertEqual(check_output('pure',0,b'DEFAULT_NATIVE pure 16\n'),[])
  self.assertTrue(check_output('pure',0,b'{"status":"pass"}'))
  self.assertTrue(check_output('missing',0,b'DEFAULT_NATIVE missing 16\n'))
 def test_missing_evidence_rejected(self):self.assertTrue(audit(ROOT/'.cache/no-default-abi.json'))

class DefaultAbiArtifactTests(unittest.TestCase):
 def test_tampering_and_forged_replay_are_rejected(self):
  import tempfile,json
  from unittest.mock import patch
  from types import SimpleNamespace
  import runtime_default_abi_evidence as abi
  from prepare_nvcc_probe import digest
  with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as temporary:
   root=Path(temporary);folder=root/'.cache/p09a2c-build/test';folder.mkdir(parents=True)
   for name in abi.INPUTS:
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'CT source')
   producer=root/'.cache/base.json';producer.write_bytes(b'CT producer')
   artifacts={}
   for role,name in abi.ROLES.items():
    p=folder/name;p.write_bytes(('CT '+role).encode());artifacts[role]={'path':p.relative_to(root).as_posix(),'sha256':digest(p)}
   m={'case_id':'arc.runtime_default_abi','source_tree':'fixed','inputs':{n:digest(root/n) for n in abi.INPUTS},'producer':{'path':producer.relative_to(root).as_posix(),'sha256':digest(producer)},'artifacts':artifacts,'observations':{}}
   for mode in ('reference','declared',*abi.MODES):
    bundle=folder/mode;bundle.mkdir();payloads={} if mode in ('reference','declared') else {'host.exe':'native','cudart64_12.dll':'runtime'}
    if mode in ('missing','forwarded'):payloads['nvcuda.dll']=mode
    if mode=='forwarded':payloads['ct_foreign.dll']='foreign'
    for name,role in payloads.items():(bundle/name).write_bytes((root/artifacts[role]['path']).read_bytes())
    out=folder/(mode+'.stdout');out.write_bytes(abi.EXPECTED if mode in ('reference','declared') else ('DEFAULT_NATIVE '+mode+(' 16\n' if mode=='pure' else ' 19\n')).encode())
    m['observations'][mode]={'stdout':out.relative_to(root).as_posix(),'sha256':digest(out),'exit_code':0,'payloads':payloads}
   path=folder/'manifest.json';path.write_text(json.dumps(m))
   with patch.object(abi,'source_fingerprint',return_value='fixed'),patch.object(abi,'audit_probe',return_value=[]):
    self.assertEqual(abi.audit(path,root),[])
    runtime=folder/abi.ROLES['runtime'];original=runtime.read_bytes();runtime.write_bytes(b'changed')
    self.assertEqual(abi.audit(path,root),['ABI artifact changed']);runtime.write_bytes(original)
    def replay(command,**kwargs):
     reference=Path(command[0]).name in (abi.ROLES['reference'],abi.ROLES['declared'])
     return SimpleNamespace(returncode=0 if reference else 42,stdout=abi.EXPECTED if reference else b'old21 DLL')
    with patch.object(abi.subprocess,'run',side_effect=replay):self.assertEqual(abi.audit(path,root,execute=True),['ABI independent replay failed'])
