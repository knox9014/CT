import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_queued_copy import validate_kernel,validate_control
class QueuedCopyResults(unittest.TestCase):
    def test_independent_kernel_oracle_checks_all_stream_rows_and_words(self):
        seed=123;rows=[[(((((seed+mode*31)*7919+i*1237)&0xffffffff)^0xa5a55a5a)+17)&0xffffffff for i in range(32)] for mode in range(3)]
        value=dict(status='pass',seed=seed,results=rows);self.assertTrue(validate_kernel(value,seed))
        import copy
        for row,index in [(0,0),(1,17),(2,31)]:
            bad=copy.deepcopy(value);bad['results'][row][index]^=1;self.assertFalse(validate_kernel(bad,seed))
        self.assertFalse(validate_kernel(dict(value,seed=True),seed));self.assertFalse(validate_kernel(dict(value,extra=1),seed))
    def test_cleanup_and_loader_controls_require_exact_errors(self):
        self.assertTrue(validate_control('absent',dict(status='pass',error=35)))
        good=dict(status='pass',error=1,cleanup=True,context_preserved=True)
        self.assertTrue(validate_control('rejected_copy',good))
        for field,value in [('error',True),('error',0),('cleanup',False),('context_preserved',1)]:
            bad=dict(good);bad[field]=value;self.assertFalse(validate_control('rejected_copy',bad))
        self.assertFalse(validate_control('unknown',good))
