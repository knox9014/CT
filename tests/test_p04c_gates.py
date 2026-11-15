import sys,unittest
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from run_validation import steps,configuration
from test_p04a_gates import OLD_CASES,NEW as P04A
from test_p04b_gates import NEW as P04B,synthetic_producer_root
NEW={'validator.global_u64','arc.runtime_global_u64'}
class WideGateTests(unittest.TestCase):
    def test_exact52_preserves_every_existing50(self):
        ids=[n for n,_,_ in steps('combined',Path('validator'),Path('lock'))]
        self.assertEqual(len(ids),52)
        self.assertEqual(set(ids),set(OLD_CASES)|P04A|P04B|NEW)
    def test_u64_configuration_binds_producer_profile_and_sources(self):
        from run_p04c_smoke import SOURCES
        selected=[s for s in steps('combined',Path('validator'),Path('lock')) if s[0] in NEW]
        with synthetic_producer_root(SOURCES) as (root,producer):
            cfg=configuration(root,'combined',selected)
            expected=hashlib.sha256(producer.read_bytes()).hexdigest()
            producer.write_bytes(b'{"scope":"changed_synthetic_configuration_test"}\n')
            changed=configuration(root,'combined',selected)
        self.assertEqual(len(cfg['cases']),2)
        native=next(c for c in cfg['cases'] if c['case_id']=='arc.runtime_global_u64')
        changed_native=next(c for c in changed['cases'] if c['case_id']=='arc.runtime_global_u64')
        self.assertEqual(native['artifact_requirements']['p04c_producer'],expected)
        self.assertNotEqual(native['artifact_requirements']['p04c_producer'],changed_native['artifact_requirements']['p04c_producer'])
        self.assertIn('p04c_producer',native['artifact_requirements'])
        self.assertIn('runtime_profile',native['artifact_requirements'])
        self.assertIn('cuda-nvcc-producer',native['tool_ids'])
