import copy
from pathlib import Path
import sys, unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from p04a_runtime_check import expected, validate
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_p04a_smoke import CASES
class GlobalOracleTests(unittest.TestCase):
    def test_independent_sequence_and_guards(self):
        good=expected(17);self.assertEqual(validate(good,17),[])
        for path in [('runs',0,64),('runs',1,0),('runs',99,144),('inputs',64),('errors',0)]:
            bad=copy.deepcopy(good);slot=bad
            for key in path[:-1]:slot=slot[key]
            slot[path[-1]]^=1
            self.assertTrue(validate(bad,17))
        bad=copy.deepcopy(good);bad['runs'][1]=bad['runs'][0];self.assertTrue(validate(bad,17))
        bad=copy.deepcopy(good);bad['extra']=True;self.assertTrue(validate(bad,17))
    def test_primary_global_fixture_uses_default_device_runtime(self):
        self.assertEqual([(stem,exe,default) for stem,exe,default in CASES if stem=='global_runtime'], [('global_runtime','host',True)])
    def test_seed_is_bound(self):self.assertTrue(validate(expected(18),17))
if __name__=='__main__': unittest.main()
