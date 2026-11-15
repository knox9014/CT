import importlib.util
from pathlib import Path
import unittest
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('kernel_abi',ROOT/'scripts/runtime_kernel_abi_evidence.py')
abi=importlib.util.module_from_spec(spec)
class KernelAbiEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if Path(spec.origin).is_file(): spec.loader.exec_module(abi)
    def test_native_output_is_exact_not_success_json(self):
        self.assertTrue(hasattr(abi,'check_output'))
        self.assertEqual(abi.check_output('pure',0,b'KERNEL_NATIVE pure 9\n'),[])
        self.assertTrue(abi.check_output('pure',0,b'{"status":"pass"}'))
        self.assertTrue(abi.check_output('missing',0,b'KERNEL_NATIVE missing 9\n'))
        self.assertTrue(abi.check_output('pure',42,b'KERNEL_NATIVE pure 9\n'))
    def test_missing_or_forged_abi_evidence_rejected(self):
        self.assertTrue(hasattr(abi,'audit'))
        self.assertTrue(abi.audit(ROOT/'.cache/no-such-kernel-abi-manifest.json'))
if __name__=='__main__':unittest.main()
