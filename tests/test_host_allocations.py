import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_host_allocations import validate_result
class HostResults(unittest.TestCase):
    def test_positive_requires_full_guarded_storage(self):
        v=dict(status='pass',checked_bytes=1028,host_allocations=2,guards=True)
        self.assertTrue(validate_result('positive',v))
        for field,value in [('checked_bytes',0),('checked_bytes',True),('host_allocations',1),('guards',1),('status','fail')]:
            bad=dict(v);bad[field]=value;self.assertFalse(validate_result('positive',bad))
        self.assertFalse(validate_result('positive',dict(v,extra=1)))
    def test_optional_controls_require_runtime35(self):
        for mode in ('missing_alloc','missing_free','forwarded_alloc','forwarded_free','absent'):
            self.assertTrue(validate_result(mode,dict(status='pass',error=35)))
            for value in (0,999,True):self.assertFalse(validate_result(mode,dict(status='pass',error=value)))
        self.assertFalse(validate_result('unknown',dict(status='pass',error=35)))
