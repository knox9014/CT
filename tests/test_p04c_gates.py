import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from run_validation import steps,configuration
from test_p04a_gates import OLD_CASES,NEW as P04A
from test_p04b_gates import NEW as P04B
NEW={'validator.global_u64','arc.runtime_global_u64'}
class WideGateTests(unittest.TestCase):
    def test_exact52_preserves_every_existing50(self):
        ids=[n for n,_,_ in steps('combined',Path('validator'),Path('lock'))]
        self.assertEqual(len(ids),52)
        self.assertEqual(set(ids),set(OLD_CASES)|P04A|P04B|NEW)
    def test_u64_configuration_binds_producer_profile_and_sources(self):
        selected=[s for s in steps('combined',Path('validator'),Path('lock')) if s[0] in NEW]
        cfg=configuration(ROOT,'combined',selected)
        self.assertEqual(len(cfg['cases']),2)
        native=next(c for c in cfg['cases'] if c['case_id']=='arc.runtime_global_u64')
        self.assertIn('p04c_producer',native['artifact_requirements'])
        self.assertIn('runtime_profile',native['artifact_requirements'])
        self.assertIn('cuda-nvcc-producer',native['tool_ids'])
