import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from static_shared_check import validate_result

class SharedOracleTests(unittest.TestCase):
    def test_all_lanes_and_both_types_have_independent_expected_values(self):
        seed=193;integers=[];floats=[]
        for threads,blocks in ((64,3),(128,4)):
            ints=[];fs=[]
            for block in range(blocks):
                original=[((seed*7919+(block*threads+t)*1237)&0xffffffff)^0xa5a55a5a for t in range(threads)]
                second=[(original[(t+1)%threads]+17)&0xffffffff for t in range(threads)]
                first=[second[(t+1)%threads]^0x3c3c3c3c for t in range(threads)]
                ints.extend((first[(t+1)%threads]+29)&0xffffffff for t in range(threads))
                # Apply the permutation directly to the bounded exact-F32 input.
                fs.extend(float(seed%997+block*threads+(t+3)%threads+15) for t in range(threads))
            integers.append(ints);floats.append(fs)
        result=dict(status='pass',seed=seed,integers=integers,floats=floats)
        self.assertTrue(validate_result(result,seed))
        integers[-1][-1]^=1;self.assertFalse(validate_result(result,seed));integers[-1][-1]^=1
        floats[-1][-1]+=1;self.assertFalse(validate_result(result,seed));floats[-1][-1]-=1
        integers[0][0]=True;self.assertFalse(validate_result(result,seed))

    def test_malformed_results_are_rejected(self):
        for result in (None,{},dict(status='pass',seed=True,integers=[],floats=[])):
            self.assertFalse(validate_result(result,1))
        self.assertFalse(validate_result({},True))

if __name__=='__main__':unittest.main()
