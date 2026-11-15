from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from device_total_check import validate


class DeviceTotalChecks(unittest.TestCase):
    def test_only_exact_native_scope_is_accepted(self):
        value=dict(status='pass',checks=39,total_bytes=1<<40,device_name='Intel synthetic',tls_preserved=True,canaries=True,unloaded=True,forwarded=False)
        validate(value,forwarded=False)
        for key,bad in (('total_bytes',0),('total_bytes',True),('total_bytes',1<<64),('checks',True),('checks',40),('tls_preserved',False),('canaries',False),('unloaded',False),('forwarded',True)):
            changed=dict(value);changed[key]=bad
            with self.assertRaises(ValueError):validate(changed,forwarded=False)
        changed=dict(value);changed['forwarded']=True;changed['checks']=42
        validate(changed,forwarded=True)
        changed=dict(value);changed['application_supported']=True
        with self.assertRaises(ValueError):validate(changed,forwarded=False)


if __name__=='__main__':unittest.main()
