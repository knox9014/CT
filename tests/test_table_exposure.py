import copy
import ctypes as c
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from table_exposure_observer import ExposureObserver, NEXT, validate_layout
from export_reject_observer import IDS,ExportRejectObserver
from table_exposure_check import expected_prefix, validate_prefix,validate


def observer():
    o=ExposureObserver.__new__(ExposureObserver)
    o.trace=[];o.callback_failures=[];o.guard_hits=[];o.blocked_callbacks=[];o.contract_mode=False;o.phase=0;o.sample=12000
    o.owner=Mock(address=0x100100);o.owner.state.return_value=dict(mask=0,stopped=0,reserved=0)
    return o


class ExposureTests(unittest.TestCase):
    def test_layout_requires_inside_image_callable_slots_and_zero_holes(self):
        words=[0]*13;words[0]=104
        for i in (1,2,4,6,7,8,12):words[i]=0x101000+16*i
        validate_layout(0x100000,0x10000,0x100100,words)
        for slot,bad in [(0,13),(3,0x101000),(6,0),(12,0x500000)]:
            changed=words.copy();changed[slot]=bad
            with self.assertRaises(ValueError):validate_layout(0x100000,0x10000,0x100100,changed)
        for pointer in (0x100101,0x10fff0,0xFFFFFF):
            with self.assertRaises(ValueError):validate_layout(0x100000,0x10000,pointer,words)

    def test_only_reviewed_post_init_query_exposes_pointer(self):
        o=observer();out=c.c_void_p(123)
        def query(uuid):
            data=c.create_string_buffer(bytes.fromhex(uuid))
            return o.reject_export(c.pointer(out),c.cast(data,c.c_void_p))
        self.assertEqual(query(IDS[0]),801);self.assertIsNone(out.value)
        o.trace.extend(expected_prefix(12000)[1:4])
        self.assertEqual(query(IDS[1]),0);self.assertEqual(out.value,o.owner.address)
        self.assertEqual(query(NEXT),801);self.assertIsNone(out.value)
        validate_prefix(o.trace,dict(status='returned',code=801,value=-1),12000)

    def test_null_unknown_or_wrong_order_never_exposes(self):
        o=observer();out=c.c_void_p(123)
        self.assertEqual(o.reject_export(c.pointer(out),None),1);self.assertIsNone(out.value)
        self.assertEqual(o.reject_export(None,123),1)
        for uuid in (IDS[1],NEXT,'00'*16):
            o=observer();out=c.c_void_p(123);data=c.create_string_buffer(bytes.fromhex(uuid))
            self.assertEqual(o.reject_export(c.pointer(out),c.cast(data,c.c_void_p)),999)
            self.assertIsNone(out.value);self.assertTrue(o.callback_failures)

    def test_latch_blocks_forwarding_and_post_init_precondition(self):
        o=observer();o.owner.state.return_value=dict(mask=1,stopped=1,reserved=0)
        self.assertTrue(o._forwarding_blocked());self.assertTrue(o.callback_failures)
        o=observer();o.phase=1;out=c.c_void_p(123);data=c.create_string_buffer(bytes.fromhex(IDS[1]))
        self.assertEqual(o.reject_export(c.pointer(out),c.cast(data,c.c_void_p)),999);self.assertIsNone(out.value)

    def test_finite_outcome_and_query_order(self):
        trace=expected_prefix(12000);validate_prefix(trace,dict(status='returned',code=801,value=-1),12000)
        for code in (0,35,36,999,True):
            with self.assertRaises(ValueError):validate_prefix(trace,dict(status='returned',code=code,value=-1),12000)
        for changed in (trace[:-1],list(reversed(trace)),trace+[trace[-1]],expected_prefix(12090)):
            with self.assertRaises(ValueError):validate_prefix(changed,dict(status='returned',code=801,value=-1),12000)

    def test_snapshot_failure_does_not_skip_iat_restore(self):
        o=observer();o.restored=False;o.owner.state.side_effect=ValueError('test')
        with patch.object(ExportRejectObserver,'restore',return_value=None) as restore:o.restore()
        restore.assert_called_once();self.assertTrue(o.callback_failures)

    def test_complete_evidence_rejects_private_hits_and_unload_failures(self):
        lookup=dict(kind='resolver_v2',symbol='cuGetExportTable',version=3000,flags=0,result=0,status=None,found=False)
        surface=dict(kind='export_surface_intervention',symbol='cuGetExportTable',version=3000,flags=0,original_result=0,original_found=False,
                     original_status=None,presented_result=0,presented_found=True,presented_status=None)
        value=dict(scope='ct_cudart_table_exposure',sample=12000,application_supported=False,shipping_version_authorized=False,
                   actual_version_before=dict(code=801,value=0),actual_version_after=dict(code=801,value=0),
                   result=dict(status='returned',code=801,value=-1),prefix_trace=[lookup,surface]+expected_prefix(12000),teardown_trace=[],
                   guard_hits=[],callback_failures=[],blocked_callbacks=[],restored=True,patches=1,restore_error=None,
                   runtime_unload=dict(free_succeeded=True,module_absent=True),context_after=dict(code=0,is_null=True),
                   fixture_before=dict(mask=0,stopped=0,reserved=0),fixture_prefix=dict(mask=0,stopped=0,reserved=0),
                   fixture_after_runtime=dict(mask=0,stopped=0,reserved=0),fixture_unload=dict(free_succeeded=True,module_absent=True))
        value['fixture_sha256']='a'*64
        self.assertEqual(validate(value)['export_queries'],3)
        for key in ('fixture_before','fixture_prefix','fixture_after_runtime'):
            changed=copy.deepcopy(value);changed[key]['mask']=1
            with self.assertRaises(ValueError):validate(changed)
        changed=copy.deepcopy(value);changed['fixture_unload']['module_absent']=False
        with self.assertRaises(ValueError):validate(changed)
        changed=copy.deepcopy(value);changed.pop('fixture_sha256')
        with self.assertRaises(ValueError):validate(changed)


if __name__=='__main__':unittest.main()
