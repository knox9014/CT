import copy
import ctypes as c
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from primary_runtime_check import expected_prefix,validate_prefix,validate_states,validate
from primary_runtime_observer import PrimaryObserver,NativeState


class ContextBridgeTests(unittest.TestCase):
    def test_foreign_lookup_does_not_apply_cuda_guard_to_inflight_context(self):
        o=PrimaryObserver.__new__(PrimaryObserver);o.phase=3;o.boundary_seen=False
        o.callback_failures=[];o.guard_hits=[];o.contract_mode=False;o.trace=[];o.state_failures=[];o.current_lookup=None
        o.foreign_lookups=[];o.callbacks=[];o.provider=Mock(_handle=0x20000);o.owner=Mock()
        o.owner.state.return_value=dict(mask=0,stopped=0,reserved=0)
        o.owner.native_state.return_value=dict(calls=1,result=0,nonnull=0)
        called=[]
        def original(handle,symbol):called.append(handle);return 0x123456
        signature=c.WINFUNCTYPE(c.c_void_p,c.c_void_p,c.c_void_p)
        callback=o.scoped_lookup(lambda original:o._callback('lookup',signature,original,failure=None),original)
        symbol=c.create_string_buffer(b'FlsGetValue');address=c.cast(symbol,c.c_void_p)
        self.assertEqual(callback(0x30000,address),0x123456)
        self.assertEqual(called,[0x30000]);self.assertFalse(o.callback_failures)
        self.assertIsNone(callback(0x20000,address))
        self.assertEqual(called,[0x30000]);self.assertTrue(o.callback_failures)
        self.assertTrue(o.state_failures[-1]['lookup']['same_provider'])

    def test_counter_layout_and_post_boundary_latch(self):
        self.assertEqual(c.sizeof(NativeState),16)
        o=PrimaryObserver.__new__(PrimaryObserver);o.phase=3;o.boundary_seen=False
        o.callback_failures=[];o.guard_hits=[];o.contract_mode=False;o.trace=[];o.state_failures=[];o.current_lookup=None
        o.owner=Mock();o.owner.state.return_value=dict(mask=0,stopped=0,reserved=0)
        o.owner.native_state.return_value=dict(calls=1,result=0,nonnull=1)
        self.assertFalse(o._forwarding_blocked())
        o.boundary_seen=True;self.assertTrue(o._forwarding_blocked())
        self.assertFalse(o.callback_failures)
        o.boundary_seen=False;o.owner.native_state.return_value=dict(calls=2,result=0,nonnull=1)
        self.assertTrue(o._forwarding_blocked());self.assertTrue(o.callback_failures)
        self.assertEqual(o.state_failures,[dict(native=dict(calls=2,result=0,nonnull=1),phase=3,lookup=None)])

    def test_exact_context_then_name_stop_is_not_runtime_success(self):
        trace=expected_prefix(12000)
        validate_prefix(trace,dict(status='returned',code=3,value=-1),12000)
        for code in (0,801,999,True):
            with self.assertRaises(ValueError):validate_prefix(trace,dict(status='returned',code=code,value=-1),12000)
        for changed in (trace[:-1],trace+[trace[-1]],expected_prefix(12090)):
            with self.assertRaises(ValueError):validate_prefix(changed,dict(status='returned',code=3,value=-1),12000)

    def test_no_deny_or_duplicate_context_is_allowed(self):
        value=dict(deny_before=dict(mask=0,stopped=0,reserved=0),deny_prefix=dict(mask=0,stopped=0,reserved=0),
                   deny_after_runtime=dict(mask=0,stopped=0,reserved=0),native_before=dict(calls=0,result=0,nonnull=0),
                   native_prefix=dict(calls=1,result=0,nonnull=1),native_after_runtime=dict(calls=1,result=0,nonnull=1),
                   primary_before_reset=dict(code=0,flags=0,active=0),primary_reset_code=0,
                   primary_after_reset=dict(code=0,flags=0,active=0),current_after_reset=dict(code=0,is_null=True))
        validate_states(value)
        for key,field,bad in (('deny_prefix','mask',2),('native_prefix','calls',2),('native_prefix','result',801),
                              ('native_after_runtime','nonnull',0),('primary_before_reset','active',1),('native_prefix','calls',True)):
            changed=copy.deepcopy(value);changed[key][field]=bad
            with self.assertRaises(ValueError):validate_states(changed)
        changed=copy.deepcopy(value);changed['primary_reset_code']=801
        with self.assertRaises(ValueError):validate_states(changed)

    def test_full_metadata_retains_public_guards_and_runtime_teardown(self):
        lookup=dict(kind='resolver_v2',symbol='cuGetExportTable',version=3000,flags=0,result=0,status=None,found=False)
        surface=dict(kind='export_surface_intervention',symbol='cuGetExportTable',version=3000,flags=0,original_result=0,original_found=False,
                     original_status=None,presented_result=0,presented_found=True,presented_status=None)
        v=dict(scope='ct_primary_runtime_bridge',sample=12000,application_supported=False,shipping_version_authorized=False,
               state_failures=[],foreign_lookups=[],
               actual_version_before=dict(code=801,value=0),actual_version_after=dict(code=801,value=0),result=dict(status='returned',code=3,value=-1),
               prefix_trace=[lookup,surface]+expected_prefix(12000),teardown_trace=[],guard_hits=[],callback_failures=[],blocked_callbacks=[],
               restored=True,patches=1,restore_error=None,runtime_unload=dict(free_succeeded=True,module_absent=True),context_after=dict(code=0,is_null=True),
               deny_before=dict(mask=0,stopped=0,reserved=0),deny_prefix=dict(mask=0,stopped=0,reserved=0),deny_after_runtime=dict(mask=0,stopped=0,reserved=0),
               native_before=dict(calls=0,result=0,nonnull=0),native_prefix=dict(calls=1,result=0,nonnull=1),native_after_runtime=dict(calls=1,result=0,nonnull=1),
               primary_before_reset=dict(code=0,flags=0,active=0),primary_reset_code=0,primary_after_reset=dict(code=0,flags=0,active=0),
               current_after_reset=dict(code=0,is_null=True))
        self.assertTrue(validate(v)['private_runtime_prefix_connected'])
        for key,bad in (('blocked_callbacks',['late']),('callback_failures',['error']),('shipping_version_authorized',True)):
            changed=copy.deepcopy(v);changed[key]=bad
            with self.assertRaises(ValueError):validate(changed)
        changed=copy.deepcopy(v);changed['runtime_unload']['module_absent']=False
        with self.assertRaises(ValueError):validate(changed)


if __name__=='__main__':unittest.main()
