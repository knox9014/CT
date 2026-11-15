import json,sys,tempfile,unittest
import hashlib
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from run_validation import steps,runtime_evidence,clear_runtime_evidence,configuration
from test_p04a_gates import OLD_CASES,NEW as P04A
NEW={'arc.runtime_symbol_abi','arc.runtime_symbol'}
@contextmanager
def synthetic_producer_root(sources):
 with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
  root=Path(name)
  for path in set(sources)|{'docs/compatibility/producer-corpus-v1.json','docs/compatibility/runtime-profile-v1.json'}:
   dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/path).read_bytes())
  producer=root/'.cache/p09a2-producer/manifest.json';producer.parent.mkdir(parents=True)
  producer.write_bytes(b'{"scope":"synthetic_configuration_test"}\n')
  yield root,producer

class SymbolGateTests(unittest.TestCase):
 def test_exact50_preserves_every_existing48(self):
  selected=steps('combined',Path('validator'),Path('lock'));ids=[n for n,_,_ in selected]
  self.assertTrue((set(OLD_CASES)|P04A|NEW)<=set(ids));self.assertEqual(len(ids),len(set(ids)))
  commands={n:c for n,_,c in selected}
  self.assertIn('--abi-only',commands['arc.runtime_symbol_abi']);self.assertNotIn('--abi-only',commands['arc.runtime_symbol'])
 def test_symbol_capture_is_required_and_old_pointer_is_cleared(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
   folder=Path(name);fake=folder/'root';(fake/'.cache').mkdir(parents=True)
   for case,label,pointer in [('arc.runtime_symbol_abi','symbol-abi','p04b-symbol-abi-latest.json'),('arc.runtime_symbol','symbol-native','p04b-symbol-latest.json')]:
    (folder/('runtime-'+label+'-manifest.json')).write_text('{"status":"pass"}')
    self.assertTrue(runtime_evidence(folder,ROOT,case))
    p=fake/'.cache'/pointer;p.write_text('{"manifest":"stale"}');clear_runtime_evidence(fake,case);self.assertFalse(p.exists())
 def test_configuration_binds_current_symbol_inputs(self):
  from run_p04b_smoke import SOURCES
  selected=[x for x in steps('arc',Path('validator'),Path('lock')) if x[0] in NEW]
  with synthetic_producer_root(SOURCES) as (root,producer):
   cfg=configuration(root,'arc',selected)
   expected=hashlib.sha256(producer.read_bytes()).hexdigest()
   producer.write_bytes(b'{"scope":"changed_synthetic_configuration_test"}\n')
   changed=configuration(root,'arc',selected)
  for before,after in zip(cfg['cases'],changed['cases']):
   self.assertEqual(before['artifact_requirements']['p04b_producer'],expected)
   self.assertNotEqual(before['artifact_requirements']['p04b_producer'],after['artifact_requirements']['p04b_producer'])
  self.assertEqual(len(cfg['cases']),2)
  for row in cfg['cases']:
   self.assertEqual(row['parameters']['producer_host_profile'],'diagnostic')
   self.assertIn('p04b_producer',row['artifact_requirements'])
   self.assertIn('runtime_profile',row['artifact_requirements'])
   self.assertGreater(len(row['artifact_requirements']),20)
   self.assertIn('cuda-nvcc-producer',row['tool_ids'])
