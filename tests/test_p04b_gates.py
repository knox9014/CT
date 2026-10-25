import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from run_validation import steps,runtime_evidence,clear_runtime_evidence,configuration
from test_p04a_gates import OLD_CASES,NEW as P04A
NEW={'arc.runtime_symbol_abi','arc.runtime_symbol'}
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
  selected=[x for x in steps('arc',Path('validator'),Path('lock')) if x[0] in NEW]
  cfg=configuration(ROOT,'arc',selected)
  self.assertEqual(len(cfg['cases']),2)
  for row in cfg['cases']:
   self.assertEqual(row['parameters']['producer_host_profile'],'diagnostic')
   self.assertIn('p04b_producer',row['artifact_requirements'])
   self.assertIn('runtime_profile',row['artifact_requirements'])
   self.assertGreater(len(row['artifact_requirements']),20)
   self.assertIn('cuda-nvcc-producer',row['tool_ids'])
