"""Finite diagnostic surface, never a successful private table."""
import ctypes as c
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from export_reject_observer import ExportRejectObserver, IDS
from real_bootstrap_observer import GuardedObserver
from export_reject_check import reject_prefix, rejection


def bare():
    o=ExportRejectObserver.__new__(ExportRejectObserver)
    o.trace=[];o.callback_failures=[];o.guard_hits=[];o.contract_mode=False;o.blocked_callbacks=[]
    o.export_callback=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_void_p),c.c_void_p)(lambda output,uuid:801)
    return o


class SurfaceTests(unittest.TestCase):
    def test_constructed_callback_clears_output_when_already_blocked(self):
        for reason in ('failure','guard'):
            o=bare();signature=c.WINFUNCTYPE(c.c_int,c.c_char_p,c.POINTER(c.c_void_p),c.c_int,c.c_uint64,c.POINTER(c.c_int))
            inner=signature(lambda *args:0);o.bindings={b'cuGetProcAddress_v2':(inner,inner)};o.callbacks=[]
            with patch.object(GuardedObserver,'_wrappers',return_value=None):o._wrappers()
            if reason=='failure':o.callback_failures=['test_failure']
            else:o.guard_hits=[dict(kind='guard')]
            out=c.c_void_p(123)
            self.assertEqual(o.export_callback(c.pointer(out),123),999)
            self.assertIsNone(out.value)

    def test_only_exact_v2_missing_result_is_presented(self):
        o=bare();out=c.c_void_p();status=c.c_int(1)
        self.assertEqual(o.present_export(b'cuGetExportTable',c.pointer(out),3000,0,c.pointer(status),0),0)
        self.assertEqual(out.value,c.cast(o.export_callback,c.c_void_p).value)
        self.assertEqual(status.value,0)
        self.assertEqual(o.trace[-1],dict(kind='export_surface_intervention',symbol='cuGetExportTable',version=3000,flags=0,original_result=0,original_found=False,original_status=1,presented_result=0,presented_found=True,presented_status=0))
        o=bare();out=c.c_void_p();self.assertEqual(o.present_export(b'cuGetExportTable',c.pointer(out),3000,0,None,0),0)
        self.assertIsNone(o.trace[-1]['original_status'])
        self.assertIsNone(o.trace[-1]['presented_status'])

    def test_unexpected_target_preconditions_latch_and_clear(self):
        for version,flags,result,pointer,status in [(3001,0,0,None,1),(3000,2,801,None,1),(3000,0,0,123,0),(3000,0,0,None,2),(3000,0,500,None,1),(3000,0,True,None,1)]:
            with self.subTest(version=version,flags=flags,result=result,pointer=pointer,status=status):
                o=bare();out=c.c_void_p(pointer);s=c.c_int(status)
                self.assertEqual(o.present_export(b'cuGetExportTable',c.pointer(out),version,flags,c.pointer(s),result),999)
                self.assertIsNone(out.value);self.assertEqual(s.value,1);self.assertTrue(o.callback_failures)
        o=bare();self.assertEqual(o.present_export(b'cuGetExportTable',None,3000,0,None,1),999)

    def test_other_symbols_are_untouched(self):
        o=bare();out=c.c_void_p(77);status=c.c_int(2)
        self.assertEqual(o.present_export(b'cuOther',c.pointer(out),1,2,c.pointer(status),500),500)
        self.assertEqual((out.value,status.value,o.trace),(77,2,[]))

    def test_callback_clears_outputs_null_short_circuit_and_known_ids(self):
        o=bare();out=c.c_void_p(123)
        with patch('export_reject_observer.c.string_at',side_effect=AssertionError('null UUID must not be read')):
            self.assertEqual(o.reject_export(c.pointer(out),None),1)
            self.assertIsNone(out.value)
            self.assertEqual(o.reject_export(None,123),1)
        for uuid in IDS:
            buffer=c.create_string_buffer(bytes.fromhex(uuid));out=c.c_void_p(123)
            self.assertEqual(o.reject_export(c.pointer(out),c.cast(buffer,c.c_void_p)),801)
            self.assertIsNone(out.value);self.assertEqual(o.trace[-1]['uuid'],uuid)
        self.assertFalse(o.guard_hits);self.assertFalse(o.callback_failures)

    def test_unknown_uuid_or_read_exception_invalidates_callback(self):
        o=bare();buffer=c.create_string_buffer(bytes(16));out=c.c_void_p(123)
        self.assertEqual(o.reject_export(c.pointer(out),c.cast(buffer,c.c_void_p)),999)
        self.assertIsNone(out.value);self.assertTrue(o.callback_failures)
        o=bare();out=c.c_void_p(123)
        with patch('export_reject_observer.c.string_at',side_effect=ValueError('test read failure')):
            wrapped=o._callback('export_reject',c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_void_p),c.c_void_p),o.reject_export)
            self.assertEqual(wrapped(c.pointer(out),123),999)
        self.assertIsNone(out.value);self.assertTrue(o.callback_failures)


def prefix(sample=12000):
    return [dict(kind='export_rejection',symbol='cuGetExportTable',uuid=IDS[0],result=801,output_cleared=True),
            dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0),
            dict(kind='intervention',symbol='cuDriverGetVersion',original_result=801,original_value=0,presented_result=0,presented_value=sample),
            dict(kind='call',symbol='cuInit',flags=0,result=0),
            dict(kind='export_rejection',symbol='cuGetExportTable',uuid=IDS[1],result=801,output_cleared=True)]


class OutcomeTests(unittest.TestCase):
    def test_complete_evidence_requires_labelled_actual_resolution(self):
        surface=dict(kind='export_surface_intervention',symbol='cuGetExportTable',version=3000,flags=0,original_result=0,
                     original_found=False,original_status=1,presented_result=0,presented_found=True,presented_status=0)
        lookup=dict(kind='resolver_v2',symbol='cuGetExportTable',version=3000,flags=0,result=0,status=1,found=False)
        value=dict(scope='ct_export_rejection',sample=12000,application_supported=False,shipping_version_authorized=False,
                   actual_version_before=dict(code=801,value=0),actual_version_after=dict(code=801,value=0),
                   result=dict(status='returned',code=801,value=-1),prefix_trace=[lookup,surface]+prefix(),teardown_trace=[],
                   guard_hits=[],callback_failures=[],blocked_callbacks=[],restored=True,patches=1,restore_error=None,
                   runtime_unload=dict(free_succeeded=True,module_absent=True),context_after=dict(code=0,is_null=True))
        self.assertEqual(rejection(value)['export_calls'],2)
        for field,bad in [('original_found',True),('presented_status',False),('original_status',True)]:
            changed=copy.deepcopy(value);changed['prefix_trace'][1][field]=bad
            with self.assertRaises(ValueError):rejection(changed)
        changed=copy.deepcopy(value);changed['prefix_trace'].pop(0)
        with self.assertRaises(ValueError):rejection(changed)
        changed=copy.deepcopy(value);changed['prefix_trace']=prefix()+[lookup,surface]
        with self.assertRaises(ValueError):rejection(changed)
        changed=copy.deepcopy(value)
        changed['prefix_trace'].append(dict(kind='guard',symbol='cuLaunchKernel',result=801,output_cleared=False))
        with self.assertRaises(ValueError):rejection(changed)

    def test_finite_order_and_status_gate(self):
        for sample in (12000,12090):reject_prefix(prefix(sample),dict(status='returned',code=801,value=-1),sample)
        for code in (0,1,35,36,999,True):
            with self.assertRaises(ValueError):reject_prefix(prefix(),dict(status='returned',code=code,value=-1),12000)
        for trace in (list(reversed(prefix())),prefix()+[prefix()[0]],prefix()[1:],prefix(12090)):
            with self.assertRaises(ValueError):reject_prefix(trace,dict(status='returned',code=801,value=-1),12000)
        for field,value in [('uuid','0'*32),('result',0),('output_cleared',False)]:
            trace=prefix();trace[0][field]=value
            with self.assertRaises(ValueError):reject_prefix(trace,dict(status='returned',code=801,value=-1),12000)


if __name__=='__main__':unittest.main()
