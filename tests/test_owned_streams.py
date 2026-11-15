import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_owned_streams import validate_result
class OwnedStreamResults(unittest.TestCase):
    def test_kernel_result_requires_both_created_streams_and_all_elements(self):
        value=dict(status='pass',seed=123,elements=32,streams=2)
        self.assertTrue(validate_result(value,123))
        for field,replacement in [('seed',124),('elements',0),('elements',True),('streams',1),('streams',True),('status','fail')]:
            bad=dict(value);bad[field]=replacement;self.assertFalse(validate_result(bad,123))
        self.assertFalse(validate_result(dict(value,extra=1),123))
