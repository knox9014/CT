import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from uniform_control_check import validate_result

class UniformOracleTests(unittest.TestCase):
    def test_zero_and_repeated_rounds_and_every_lane_are_checked(self):
        for seed in (193,780927):
            integers=[];floats=[]
            for threads,blocks,rounds in ((64,2,0),(64,3,3),(128,4,5)):
                ints=[];fs=[]
                for i in range(threads*blocks):
                    j=i//threads*threads+(i%threads+2*rounds)%threads
                    v=(seed*7919+j*1237)&0xffffffff
                    for _ in range(rounds):v=(((v^0xa5a55a5a)+17)&0xffffffff)^0x3c3c3c3c
                    ints.append((v+29)&0xffffffff);fs.append(float(seed%997+j+rounds*7+8))
                integers.append(ints);floats.append(fs)
            value=dict(status='pass',seed=seed,integers=integers,floats=floats)
            self.assertTrue(validate_result(value,seed))
            integers[0][-1]^=1;self.assertFalse(validate_result(value,seed));integers[0][-1]^=1
            floats[-1][-1]+=1;self.assertFalse(validate_result(value,seed))
    def test_bad_schema_and_seed_are_rejected(self):
        for value in (None,{},dict(status='pass',seed=True,integers=[],floats=[])):
            self.assertFalse(validate_result(value,1))
        self.assertFalse(validate_result({},True))

if __name__=='__main__':unittest.main()
