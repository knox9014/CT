import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from p04c_global_check import expected,validate,expected_noop,validate_noop
class WideGlobalOracleTests(unittest.TestCase):
    def test_upper_bits_partial_bytes_guards_and_exact_noop(self):
        for seed in (1,773,999990):
            for order in (0,1):
                value=expected(seed,order)
                self.assertEqual(validate(value,seed,order),[])
                self.assertGreater(value['contexts'][0]['before'][0][0],0xffffffff)
                self.assertLess(value['contexts'][0]['after'][0][0],value['contexts'][0]['before'][0][0])
                for field,index in [('before',0),('runs',64),('partial_reads',0),('partial_reads',64),('partial_reads',65),('partial_reads',129)]:
                    bad=copy.deepcopy(value);bad['contexts'][0][field][0][index]^=1
                    self.assertTrue(validate(bad,seed,order))
                bad=copy.deepcopy(value);bad['contexts'][0]['before'][0][0]&=0xffffffff
                self.assertTrue(validate(bad,seed,order))
                noop=expected_noop(seed,order)
                self.assertEqual(validate_noop(noop,seed,order),[])
                self.assertTrue(validate(noop,seed,order))
                self.assertTrue(validate_noop(value,seed,order))
                bad=copy.deepcopy(noop);bad['contexts'][1]['partial_reads'][99][0]^=1
                self.assertTrue(validate_noop(bad,seed,order))
