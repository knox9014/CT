import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_driver_events import validate_control,validate_result

class DriverEventsEvidenceTests(unittest.TestCase):
    def test_control_requires_the_intended_timing_failure(self):
        self.assertTrue(validate_control('record_noop',42,b'',b'EVENT_TIMING_REJECT code=400 milliseconds=987.5\n'))
        self.assertTrue(validate_control('zero_time',42,b'',b'EVENT_TIMING_REJECT code=0 milliseconds=0\n'))
        for stderr in (b'',b'driver event line 17\n',b'EVENT_TIMING_REJECT code=999 milliseconds=987.5\n'):
            self.assertFalse(validate_control('record_noop',42,b'',stderr))
        self.assertFalse(validate_control('zero_time',42,b'',b'EVENT_TIMING_REJECT code=400 milliseconds=987.5\n'))
        self.assertFalse(validate_control('record_noop',0,b'',b'EVENT_TIMING_REJECT code=400 milliseconds=987.5\n'))
    def test_positive_observation_rejects_nonfinite_and_wrong_types(self):
        value=dict(status='pass',seed=12,milliseconds=1.5,roundtrips=8,words=1024,ownership=True,capacity=128)
        self.assertTrue(validate_result(value,12))
        for field,bad in [('milliseconds',float('nan')),('milliseconds',0),('milliseconds',True),('seed',True),('roundtrips',True),('ownership',1),('capacity',127)]:
            changed=dict(value);changed[field]=bad
            self.assertFalse(validate_result(changed,12))
        self.assertFalse(validate_result(value,13))

if __name__=='__main__':unittest.main()
