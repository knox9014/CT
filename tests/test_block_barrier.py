import sys,unittest,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from block_barrier_check import validate_result,inspect_spirv,invalid_execution_scope

def module(scope=2,semantics=784):
 w=[0x07230203,0x10000,0,20,0]
 def op(code,*a):w.append(((len(a)+1)<<16)|code);w.extend(a)
 op(15,6,10,97);op(15,6,11,98)
 op(21,3,32,0);op(43,3,6,scope);op(43,3,7,semantics)
 for fid in (10,11):
  op(54,1,fid,0,2);op(248,fid+3)
  for _ in range(3):op(224,6,6,7)
  op(253);op(56)
 return struct.pack('<'+'I'*len(w),*w)
class BlockBarrierTests(unittest.TestCase):
 def test_scopes_semantics_counts_and_corruption_are_checked(self):
  self.assertEqual(inspect_spirv(module())['per_function'],[3,3])
  for data in (module(scope=4),module(semantics=776),invalid_execution_scope(module()),module()[:-1]):
   with self.assertRaises(ValueError):inspect_spirv(data)
 def test_independent_all_lane_math_and_exact_types(self):
  seed=193;rows=[]
  for threads,blocks in ((64,3),(128,4)):
   row=[]
   for i in range(threads*blocks):
    index=(i//threads)*threads+(i%threads+2)%threads
    value=(seed*7919+index*1237)&0xffffffff
    row.append((((value^0xa5a55a5a)+17)^0x3c3c3c3c)+29 &0xffffffff)
   rows.append(row)
  value=dict(status='pass',seed=seed,results=rows)
  self.assertTrue(validate_result(value,seed));rows[1][-1]^=1;self.assertFalse(validate_result(value,seed))
  self.assertFalse(validate_result(dict(status='pass',seed=True,results=[]),True))
if __name__=='__main__':unittest.main()
