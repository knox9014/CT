"""Reject partial, mistyped or wrong native stream observations."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_default_stream_sync import validate_result

class StreamResultTests(unittest.TestCase):
    def test_positive_requires_complete_roundtrip_and_context(self):
        v=dict(status='pass',checked_bytes=1028,context_preserved=True)
        self.assertTrue(validate_result('positive',v))
        for field,value in [('checked_bytes',0),('checked_bytes',True),('context_preserved',1),('context_preserved',False),('status','fail')]:
            bad=dict(v);bad[field]=value;self.assertFalse(validate_result('positive',bad))
        self.assertFalse(validate_result('positive',dict(v,extra=1)))

    def test_controls_require_exact_errors_and_ordinary_context(self):
        self.assertTrue(validate_result('absent',dict(status='pass',error=35)))
        self.assertTrue(validate_result('sync_error',dict(status='pass',error=709,context_preserved=True)))
        for value in (True,0,35,999):
            self.assertFalse(validate_result('sync_error',dict(status='pass',error=value,context_preserved=True)))
        self.assertFalse(validate_result('sync_error',dict(status='pass',error=709,context_preserved=1)))
        self.assertFalse(validate_result('absent',dict(status='pass',error=999)))
        self.assertFalse(validate_result('unknown',dict(status='pass',error=35)))
