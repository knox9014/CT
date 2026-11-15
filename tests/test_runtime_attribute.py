"""Closed native attribute observation contract, independent of C++ assertions."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_runtime_attribute import validate_result

class AttributeResultTests(unittest.TestCase):
    def test_synchronous_profile_has_exactly_two_zero_capabilities(self):
        value=dict(status='pass',values=[256,256,256,256,65535,65535,65535,16384,0,0,0],context_unchanged=True)
        for mode in ('normal','minimal'):
            self.assertTrue(validate_result(mode,value))
            for index in (9,10):
                for replacement in (1,-1,True,None):
                    bad=copy.deepcopy(value);bad['values'][index]=replacement
                    self.assertFalse(validate_result(mode,bad))
            self.assertFalse(validate_result(mode,dict(value,values=value['values'][:9])))

    def test_positive_requires_all_eleven_values_and_unchanged_context(self):
        value=dict(status='pass',values=[256,256,256,256,65535,65535,65535,16384,0,0,0],context_unchanged=True)
        for mode in ('normal','minimal'):
            self.assertTrue(validate_result(mode,value))
        for field,replacement in [('status','fail'),('context_unchanged',1),('values',[1]*8),
                                  ('values',[1]*6+[0,16384,0,0,0]),('values',[True]*8+[0]),('values',[1]*8),
                                  ('values',[1]*7+[16385,0,0,0]),('values',[1]*7+[-1,0,0,0]),('values',[1]*7+[True,0,0,0])]:
            bad=copy.deepcopy(value);bad[field]=replacement
            self.assertFalse(validate_result('normal',bad))
        bad=dict(value,extra=1);self.assertFalse(validate_result('normal',bad))
        self.assertTrue(validate_result('normal',dict(value,values=[1]*7+[0,0,0,0])))

    def test_negative_requires_runtime_loader35(self):
        for mode in ('missing','forwarded','absent'):
            self.assertTrue(validate_result(mode,dict(status='pass',loader_error=35)))
            for code in (0,801,999,True):
                self.assertFalse(validate_result(mode,dict(status='pass',loader_error=code)))
        self.assertFalse(validate_result('unknown',dict(status='pass',loader_error=35)))
