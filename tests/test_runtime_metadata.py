import copy
import ctypes as c
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from runtime_metadata_check import expected_prefix,validate_prefix,validate
from runtime_metadata_observer import MetadataObserver


class MetadataPrefixTests(unittest.TestCase):
    def test_metadata_call_preconditions_do_not_permit_wrong_order(self):
        o=MetadataObserver.__new__(MetadataObserver);o.phase=3;o.metadata_step=0;o.trace=[];o.callback_failures=[];o.owner=Mock()
        o.owner.native_state.return_value=dict(calls=1,result=0,nonnull=1)
        output=c.pointer(c.c_int())
        self.assertTrue(o._metadata_ready(output,0,0))
        self.assertFalse(o._metadata_ready(output,1,0));self.assertTrue(o.callback_failures)

    def test_exact_actual_metadata_then_strict_refusal(self):
        value=dict(status='returned',code=3,value=-1)
        trace=expected_prefix(12000,'Intel synthetic',1<<40)
        validate_prefix(trace,value,12000,'Intel synthetic',1<<40)
        for changed in (trace[:-1],trace+[trace[-1]],expected_prefix(12090,'Intel synthetic',1<<40),expected_prefix(12000,'Intel other',1<<40)):
            with self.assertRaises(ValueError):validate_prefix(changed,value,12000,'Intel synthetic',1<<40)
        for total in (0,True,1<<64):
            with self.assertRaises(ValueError):validate_prefix(trace,value,12000,'Intel synthetic',total)

    def test_attribute_success_or_virtual_value_cannot_pass_strict_profile(self):
        value=dict(status='returned',code=3,value=-1);trace=expected_prefix(12000,'Intel synthetic',8192)
        for field,bad in (('result',0),('value',5),('attribute',76),('ordinal',1),('result',True)):
            changed=copy.deepcopy(trace);changed[-1][field]=bad
            with self.assertRaises(ValueError):validate_prefix(changed,value,12000,'Intel synthetic',8192)
        for code in (0,801,True):
            with self.assertRaises(ValueError):validate_prefix(trace,dict(status='returned',code=code,value=-1),12000,'Intel synthetic',8192)

    def test_policy_and_real_control_metadata_cannot_be_substituted(self):
        lookup=dict(kind='resolver_v2',symbol='cuGetExportTable',version=3000,flags=0,result=0,status=None,found=False)
        surface=dict(kind='export_surface_intervention',symbol='cuGetExportTable',version=3000,flags=0,original_result=0,original_found=False,
                     original_status=None,presented_result=0,presented_found=True,presented_status=None)
        v=dict(scope='ct_runtime_metadata_prefix',sample=12000,application_supported=False,shipping_version_authorized=False,
               state_failures=[],foreign_lookups=[],policy_mode='strict-default',policy_env_absent=True,
               name_control=dict(code=0,value='Intel synthetic'),memory_control=dict(code=0,total_bytes=8192),
               actual_version_before=dict(code=801,value=0),actual_version_after=dict(code=801,value=0),result=dict(status='returned',code=3,value=-1),
               prefix_trace=[lookup,surface]+expected_prefix(12000,'Intel synthetic',8192),teardown_trace=[],guard_hits=[],callback_failures=[],blocked_callbacks=[],
               restored=True,patches=1,restore_error=None,runtime_unload=dict(free_succeeded=True,module_absent=True),context_after=dict(code=0,is_null=True),
               deny_before=dict(mask=0,stopped=0,reserved=0),deny_prefix=dict(mask=0,stopped=0,reserved=0),deny_after_runtime=dict(mask=0,stopped=0,reserved=0),
               native_before=dict(calls=0,result=0,nonnull=0),native_prefix=dict(calls=1,result=0,nonnull=1),native_after_runtime=dict(calls=1,result=0,nonnull=1),
               primary_before_reset=dict(code=0,flags=0,active=0),primary_reset_code=0,primary_after_reset=dict(code=0,flags=0,active=0),current_after_reset=dict(code=0,is_null=True))
        self.assertEqual(validate(v)['actual_attribute_code'],801)
        for key,bad in (('policy_env_absent',False),('policy_mode','ct-sm52-subset-v1'),('shipping_version_authorized',True)):
            changed=copy.deepcopy(v);changed[key]=bad
            with self.assertRaises(ValueError):validate(changed)
        for key,field,bad in (('memory_control','total_bytes',8193),('memory_control','code',801),('name_control','value','Intel other'),('native_prefix','calls',2)):
            changed=copy.deepcopy(v);changed[key][field]=bad
            with self.assertRaises(ValueError):validate(changed)


if __name__=='__main__':unittest.main()
