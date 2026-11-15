import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_runtime_events import validate_native
class RuntimeEventEvidenceTests(unittest.TestCase):
 def test_complete_observations_and_exact_types(self):
  value=dict(status='pass',milliseconds=1.5,context_preserved=True)
  self.assertTrue(validate_native('positive',value))
  for bad in (float('nan'),float('inf'),0,True):
   self.assertFalse(validate_native('positive',dict(value,milliseconds=bad)))
  self.assertTrue(validate_native('absent',dict(status='pass',error=35)))
  self.assertFalse(validate_native('absent',dict(status='pass',error=True)))
  self.assertFalse(validate_native('missing_0',dict(status='pass',error=35)))
  self.assertTrue(validate_native('forwarded',dict(status='pass',error=35,core_alive=True,extension_verified=True)))
  self.assertFalse(validate_native('forwarded',dict(status='pass',error=35,core_alive=False,extension_verified=True)))
if __name__=='__main__':unittest.main()
