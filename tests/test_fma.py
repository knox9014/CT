import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fma_check import fused_bits,split_bits,matches,cases,validate_result

class FmaOracleTests(unittest.TestCase):
    def test_literal_ieee_anchors_include_fused_discriminators(self):
        for a,b,c,want in [
            (0x3f800001,0x3f7ffffe,0xbf800000,0xa8800000),
            (0x3f800000,0x3f800000,0x33800000,0x3f800000),
            (0x3f800001,0x3f800000,0x33800000,0x3f800002),
            (1,0x3f800000,0,1),(0x00800000,0x3f000000,0,0x00400000),
            (1,0x3f000000,0,0),(1,0x3f000000,1,2),
            (0x7f7fffff,0x40000000,0xff7fffff,0x7f7fffff),
            (0x7f7fffff,0x40000000,0,0x7f800000),
            (0x80000000,0x3f800000,0x80000000,0x80000000),
            (0x3f800000,0x3f800000,0xbf800000,0),
        ]:self.assertEqual(fused_bits(a,b,c),want)
        self.assertEqual(split_bits(0x3f800001,0x3f7ffffe,0xbf800000),0)
        self.assertEqual(split_bits(0x7f7fffff,0x40000000,0xff7fffff),0x7f800000)
        self.assertEqual(split_bits(1,0x3f000000,1),1)
    def test_nan_is_classification_only_and_zero_sign_is_exact(self):
        self.assertIsNone(fused_bits(0,0x7f800000,0))
        self.assertIsNone(fused_bits(0x7f800000,0x3f800000,0xff800000))
        self.assertTrue(matches(0xffc12345,None));self.assertFalse(matches(0x7f800000,None))
        self.assertFalse(matches(0,0x80000000));self.assertFalse(matches(True,1))
    def test_result_schema_checks_cpu_mode_and_corrupted_last_lane(self):
        seed=193;inputs=cases(seed);fused=[];split=[]
        for n in (192,512):
            fused.append([fused_bits(*inputs[(i+seed)%32]) for i in range(n)])
            split.append([split_bits(*inputs[(i+seed)%32]) for i in range(n)])
        for rows in (fused,split):
            for row in rows:
                for i,v in enumerate(row):
                    if v is None:row[i]=0x7fc00000
        value=dict(status='pass',seed=seed,cpu_mode=True,fused=fused,split=split)
        self.assertTrue(validate_result(value,seed))
        fused[-1][-1]^=1;self.assertFalse(validate_result(value,seed));fused[-1][-1]^=1
        value['cpu_mode']=False;self.assertFalse(validate_result(value,seed))
        self.assertFalse(validate_result({},True))

if __name__=='__main__':unittest.main()
