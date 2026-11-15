import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('kernel_check',ROOT/'tests/p09a2_kernel_check.py')
check=importlib.util.module_from_spec(spec)
class KernelEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if Path(spec.origin).is_file():spec.loader.exec_module(check)
    def test_independent_oracle_rejects_noop_guards_and_changed_inputs(self):
        self.assertTrue(hasattr(check,'verify_result'))
        seed=123
        a=[0xdecafbad]*21;b=a.copy();c=[0xa5a5a5a5]*21
        for i in range(17):a[i+2]=seed*13+i*37;b[i+2]=seed*17+i*19;c[i+2]=a[i+2]+b[i+2]+7
        value=dict(seed=seed,mode='single',errors=[],runs=[dict(seed=seed,a=a,b=b,c=c)])
        self.assertEqual(check.verify_result(value,seed,'single'),[])
        for which,index in [('a',2),('b',0),('c',2),('c',20)]:
            value['runs'][0][which][index]^=1
            self.assertTrue(check.verify_result(value,seed,'single'))
            value['runs'][0][which][index]^=1
        value['runs'][0]['c']=[0xa5a5a5a5]*21
        self.assertTrue(check.verify_result(value,seed,'single'))
        self.assertTrue(check.verify_result({'status':'pass'},seed,'single'))
    def test_missing_or_forged_native_evidence_rejected(self):
        self.assertTrue(hasattr(check,'audit_manifest'))
        self.assertTrue(check.audit_manifest(ROOT/'.cache/missing-kernel-manifest.json'))
    def test_retirement_control_has_distinct_numeric_and_error_contract(self):
        seed=123;a=[0xdecafbad]*21;b=a.copy();c=[0xa5a5a5a5]*21
        for i in range(17):a[i+2]=seed*13+i*37;b[i+2]=seed*17+i*19;c[i+2]=a[i+2]+b[i+2]
        value=dict(seed=seed,mode='retire',errors=[98],runs=[dict(seed=seed,a=a,b=b,c=c)])
        self.assertEqual(check.verify_result(value,seed,'retire'),[])
        value['errors']=[];self.assertTrue(check.verify_result(value,seed,'retire'))
if __name__=='__main__':unittest.main()
