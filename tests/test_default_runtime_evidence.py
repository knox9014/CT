import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from p09a2c_default_check import verify_result,audit_manifest
class DefaultRuntimeEvidenceTests(unittest.TestCase):
 def test_negative_requires_exact_main_error_and_seed(self):
  value={'seed':23,'mode':'used_global','errors':[801],'runs':[],'main_entered':1}
  self.assertEqual(verify_result(value,23,'used_global'),[])
  for change in ({'errors':[98]},{'main_entered':0},{'seed':24},{'runs':[{}]}):self.assertTrue(verify_result(dict(value,**change),23,'used_global'))
 def test_positive_missing_arrays_and_forged_success_fail(self):
  self.assertTrue(verify_result({'status':'pass'},23,'single'));self.assertTrue(verify_result({'seed':23,'mode':'single','errors':[],'runs':[]},23,'single'))
 def test_missing_manifest_fails(self):self.assertTrue(audit_manifest(ROOT/'.cache/no-default-native.json'))

class DefaultNumericTests(unittest.TestCase):
 def test_positive_control_noop_guard_and_input_contracts(self):
  seed=123;a=[0xdecafbad]*21;b=a.copy();c=[0xa5a5a5a5]*21
  for i in range(17):a[i+2]=seed*13+i*37;b[i+2]=seed*17+i*19;c[i+2]=a[i+2]+b[i+2]+7
  value={'seed':seed,'mode':'single','errors':[],'runs':[{'seed':seed,'a':a,'b':b,'c':c}]}
  self.assertEqual(verify_result(value,seed,'single'),[])
  for array,index in [('a',0),('b',2),('c',20),('c',2)]:
   value['runs'][0][array][index]^=1;self.assertTrue(verify_result(value,seed,'single'));value['runs'][0][array][index]^=1
  value['runs'][0]['c']=[0xa5a5a5a5]*21;self.assertTrue(verify_result(value,seed,'noop'))
  for i in range(17):c[i+2]=a[i+2]+b[i+2]
  value.update(mode='control',errors=[98],blocked_errors=[801,801],driver_calls=[0,0]);value['runs'][0]['c']=c
  self.assertEqual(verify_result(value,seed,'control'),[])
  value['driver_calls']=[0,1];self.assertTrue(verify_result(value,seed,'control'))

class DefaultControlProvenanceTests(unittest.TestCase):
 def test_blocked_symbol_must_be_an_actual_oracle_entry(self):
  from p09a2c_default_check import validate_control_symbol
  source=(ROOT/'tests/p09a2c_default_control.cpp').read_text()
  self.assertEqual(validate_control_symbol(source,'.visible .entry ct_oracle_add() {}'),[])
  self.assertTrue(validate_control_symbol(source,'.visible .entry other() {}'))
