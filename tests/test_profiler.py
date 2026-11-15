import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_profiler import validate_native
class ProfilerEvidenceTests(unittest.TestCase):
 def test_exact_mode_error_and_control_observations(self):
  for mode,code in [('positive',0),('trap_sync',1),('queued_error',1)]:
   value=dict(status='pass',mode=mode,error=code,context_preserved=True,control_verified=True)
   self.assertTrue(validate_native(mode,value))
   self.assertFalse(validate_native(mode,dict(value,error=True)))
   self.assertFalse(validate_native(mode,dict(value,control_verified=False)))
   self.assertFalse(validate_native('absent',value))
  self.assertTrue(validate_native('absent',dict(status='pass',mode='absent',error=35)))
  self.assertFalse(validate_native('absent',dict(status='pass',mode='absent',error=0)))
if __name__=='__main__':unittest.main()
