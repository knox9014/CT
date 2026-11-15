import copy
import ctypes as c
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from hooks_exposure_observer import HooksObserver,validate_hooks_layout
from hooks_exposure_check import expected_prefix,validate_prefix,validate
from table_exposure_observer import NEXT


def observer():
    o=HooksObserver.__new__(HooksObserver);o.phase=2;o.sample=12000;o.contract_mode=False
    o.trace=[];o.callback_failures=[];o.guard_hits=[];o.blocked_callbacks=[]
    o.owner=Mock(hooks_address=0x100200);o.owner.state.return_value=dict(mask=0,stopped=0,reserved=0)
    return o


class HooksTests(unittest.TestCase):
    def test_typed_hooks_layout_is_not_cudart_layout(self):
        words=[56,0,0x101000,0,0,0,0x101100]
        validate_hooks_layout(0x100000,0x10000,0x100200,words)
        for slot,bad in ((0,104),(1,0x101000),(2,0),(6,0x500000)):
            changed=words.copy();changed[slot]=bad
            with self.assertRaises(ValueError):validate_hooks_layout(0x100000,0x10000,0x100200,changed)
        with self.assertRaises(ValueError):validate_hooks_layout(0x100000,0x10000,0x10fff0,words)

    def test_exact_third_query_presents_hooks_but_not_buffers(self):
        o=observer();out=c.c_void_p(123);data=c.create_string_buffer(bytes.fromhex(NEXT))
        self.assertEqual(o.reject_export(c.pointer(out),c.cast(data,c.c_void_p)),0)
        self.assertEqual(out.value,o.owner.hooks_address);self.assertEqual(o.phase,3)
        self.assertEqual(o.trace[-1]['fixture_kind'],'hooks_deny_only')

    def test_expected_private_context_hit_blocks_without_hiding_other_hits(self):
        o=observer();o.phase=3;o.owner.state.return_value=dict(mask=2,stopped=1,reserved=0)
        self.assertTrue(o._forwarding_blocked());self.assertFalse(o.callback_failures)
        for state in (dict(mask=128,stopped=1,reserved=0),dict(mask=3,stopped=1,reserved=0),dict(mask=2,stopped=0,reserved=0)):
            o=observer();o.phase=3;o.owner.state.return_value=state
            self.assertTrue(o._forwarding_blocked());self.assertTrue(o.callback_failures)
        o=observer();o.owner.state.return_value=dict(mask=2,stopped=1,reserved=0)
        self.assertTrue(o._forwarding_blocked());self.assertTrue(o.callback_failures)

    def test_runtime_three_is_not_private_801_or_success(self):
        trace=expected_prefix(12000);validate_prefix(trace,dict(status='returned',code=3,value=-1),12000)
        for code in (0,1,35,36,801,999,True):
            with self.assertRaises(ValueError):validate_prefix(trace,dict(status='returned',code=code,value=-1),12000)
        for changed in (trace[:-1],trace+[trace[-1]],list(reversed(trace)),expected_prefix(12090)):
            with self.assertRaises(ValueError):validate_prefix(changed,dict(status='returned',code=3,value=-1),12000)

    def test_expected_hit_cannot_hide_other_callbacks_or_forwarding(self):
        lookup=dict(kind='resolver_v2',symbol='cuGetExportTable',version=3000,flags=0,result=0,status=None,found=False)
        surface=dict(kind='export_surface_intervention',symbol='cuGetExportTable',version=3000,flags=0,original_result=0,original_found=False,
                     original_status=None,presented_result=0,presented_found=True,presented_status=None)
        value=dict(scope='ct_hooks_deny_exposure',sample=12000,application_supported=False,shipping_version_authorized=False,
                   actual_version_before=dict(code=801,value=0),actual_version_after=dict(code=801,value=0),
                   result=dict(status='returned',code=3,value=-1),prefix_trace=[lookup,surface]+expected_prefix(12000),teardown_trace=[],
                   guard_hits=[],callback_failures=[],blocked_callbacks=[],restored=True,patches=1,restore_error=None,
                   runtime_unload=dict(free_succeeded=True,module_absent=True),context_after=dict(code=0,is_null=True),fixture_sha256='a'*64,
                   fixture_before=dict(mask=0,stopped=0,reserved=0),fixture_prefix=dict(mask=2,stopped=1,reserved=0),
                   fixture_after_runtime=dict(mask=2,stopped=1,reserved=0),fixture_unload=dict(free_succeeded=True,module_absent=True))
        self.assertEqual(validate(value)['private_context_entry_mask'],2)
        changed=copy.deepcopy(value);changed.pop('fixture_sha256')
        with self.assertRaises(ValueError):validate(changed)
        for key in ('fixture_prefix','fixture_after_runtime'):
            for mask in (0,128,130,True):
                changed=copy.deepcopy(value);changed[key]['mask']=mask
                with self.assertRaises(ValueError):validate(changed)
        changed=copy.deepcopy(value);changed['blocked_callbacks']=['device_get']
        with self.assertRaises(ValueError):validate(changed)
        changed=copy.deepcopy(value);changed['fixture_unload']['module_absent']=False
        with self.assertRaises(ValueError):validate(changed)


if __name__=='__main__':unittest.main()
