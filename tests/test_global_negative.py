import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from global_negative import validate_negative
class GlobalNegativeTests(unittest.TestCase):
    def test_actual_array_width_and_volatile_load_are_required(self):
        ptx='.global .align 8 .b8 ct_used_global[16]={7}; ld.volatile.global.u8 %r,[ct_used_global];'
        stub='__cudaRegisterVariable(t, __shadow_var(ct_used_global,::ct_used_global), 0, 16Ui64, 0, 0);'
        self.assertEqual(validate_negative(ptx,stub),[])
        for bad in [ptx.replace('[16]','[8]'),ptx.replace('.b8','.u64'),ptx.replace('ld.volatile.global','ld.global')]:
            self.assertTrue(validate_negative(bad,stub))
        self.assertTrue(validate_negative(ptx,stub.replace('16Ui64','8Ui64')))
