"""Real-provider version interventions remain diagnostic, not CUDA support."""
import ctypes as c
from pathlib import Path
import sys
import unittest
import copy
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from cupy_bootstrap_observer import Observer
from real_bootstrap_observer import GuardedObserver
import real_bootstrap_check as check
import run_real_bootstrap as runner
import tempfile

def observed(sample=12000,code=36):
    trace=[dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0),
           dict(kind='intervention',symbol='cuDriverGetVersion',original_result=801,original_value=0,presented_result=0,presented_value=sample),
           dict(kind='call',symbol='cuInit',flags=0,result=0)]
    if code==0:trace.append(dict(kind='call',symbol='cuDeviceGetCount',result=0,value=1))
    return dict(scope='ct_guarded_counterfactual',sample=sample,application_supported=False,shipping_version_authorized=False,
                actual_version_before=dict(code=801,value=0),actual_version_after=dict(code=801,value=0),
                result=dict(status='returned',code=code,value=1 if code==0 else -1),prefix_trace=trace,teardown_trace=[],
                guard_hits=[],callback_failures=[],blocked_callbacks=[],restored=True,patches=1,
                runtime_unload=dict(free_succeeded=True,module_absent=True),restore_error=None,context_after=dict(code=0,is_null=True))

class EvidenceTests(unittest.TestCase):
    def test_unreviewed_kernel_surface_or_mutated_input_prevents_execution(self):
        runner.kernel_surface({'cuLaunchKernel','cuModuleLoadData','cuInit'})
        with self.assertRaises(ValueError):runner.kernel_surface({'cuLaunchKernel','cuModuleLoadData','cuGraphLaunch'})
        root=Path(__file__).resolve().parents[1];(root/'.cache').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root/'.cache') as directory:
            folder=Path(directory);record=dict(source_fingerprint='s',python=str(folder/'python.exe'),python_sha256='p',artifacts={'ct_cuda.dll':'d'})
            with unittest.mock.patch.object(runner,'source_fingerprint',return_value='s'),unittest.mock.patch.object(runner,'digest',return_value='changed'),unittest.mock.patch.object(runner.subprocess,'run') as process:
                with self.assertRaises(ValueError):runner.execute(folder,record,[],folder,{})
                process.assert_not_called()

    def test_boolean_or_failed_teardown_metadata_cannot_pass(self):
        for key,value in [('runtime_unload',dict(free_succeeded=1,module_absent=True)),('context_after',dict(code=False,is_null=True))]:
            bad=observed();bad[key]=value
            with self.assertRaises(ValueError):check.counterfactual(bad,1)
    def test_blocker_is_after_real_init_and_not_successful_enumeration(self):
        out=check.counterfactual(observed(),1)
        self.assertEqual(out['runtime_code'],36);self.assertTrue(out['real_init_passed'])
        self.assertFalse(out['runtime_enumeration_passed']);self.assertFalse(out['application_supported'])

    def test_positive_enumeration_needs_actual_call_and_direct_count_agreement(self):
        value=observed(code=0)
        self.assertTrue(check.counterfactual(value,1)['runtime_enumeration_passed'])
        value['prefix_trace'].pop()
        with self.assertRaises(ValueError):check.counterfactual(value,1)
        with self.assertRaises(ValueError):check.counterfactual(observed(code=0),2)

    def test_mismatched_sample_guard_failure_or_cached_dll_cannot_pass(self):
        for key,value in [('sample',12090),('restored',False),('callback_failures',['count']),('guard_hits',[{}]),
                          ('blocked_callbacks',['init']),('runtime_unload',dict(free_succeeded=True,module_absent=False))]:
            bad=observed();bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):check.counterfactual(bad,1)

    def test_raw_calls_and_intervention_are_not_interchangeable(self):
        bad=observed();bad['prefix_trace'][0]['result']=0
        with self.assertRaises(ValueError):check.counterfactual(bad,1)

    def test_only_reviewed_negative_runtime_status_may_complete_an_arm(self):
        for code in (35,801,999):
            with self.subTest(code=code),self.assertRaises(ValueError):check.counterfactual(observed(code=code),1)
        bad=observed();bad['prefix_trace'][2]['result']=True
        with self.assertRaises(ValueError):check.counterfactual(bad,1)

class BindingTests(unittest.TestCase):
    def test_guard_latch_blocks_forwarding_except_expected_contract_child(self):
        obj=GuardedObserver.__new__(GuardedObserver);obj.callback_failures=[];obj.trace=[]
        obj.guard_hits=[{'symbol':'cuLaunchKernel'}];obj.contract_mode=False;obj.blocked_callbacks=[]
        forward=Mock(return_value=7)
        callback=obj._callback('count',c.CFUNCTYPE(c.c_int,c.POINTER(c.c_int)),forward,clear_output=0)
        output=c.c_int(-1)
        self.assertEqual(callback(c.byref(output)),999);forward.assert_not_called()
        self.assertEqual(obj.blocked_callbacks,['count'])
        obj.contract_mode=True
        self.assertEqual(callback(c.byref(output)),7);forward.assert_called_once()

    def test_only_two_fixed_samples_are_allowed(self):
        for sample in (True,0,11999,12001,13000):
            with self.assertRaises(ValueError):GuardedObserver(None,sample=sample)
        obj=GuardedObserver.__new__(GuardedObserver);obj.sample=12090;obj.trace=[];obj.callback_failures=[]
        value=c.c_int(0)
        self.assertEqual(obj._present_version(801,c.pointer(value)),0);self.assertEqual(value.value,12090)
    def test_callback_exception_is_latched_and_cannot_pass_restoration(self):
        obj=Observer.__new__(Observer);obj.callback_failures=[];obj.trace=[];obj.saved=[];obj.restored=False
        def broken(output):raise ValueError('not exposed')
        callback=obj._callback('count',c.CFUNCTYPE(c.c_int,c.POINTER(c.c_int)),broken,clear_output=0)
        output=c.c_int(71)
        self.assertEqual(callback(c.byref(output)),999);self.assertEqual(output.value,0)
        self.assertEqual(obj.callback_failures,['count'])
        with self.assertRaises(ValueError):obj.restore()
        self.assertTrue(obj.restored)

    def test_pointer_identity_is_checked_for_raw_and_versioned_self_lookup(self):
        actual=c.CFUNCTYPE(c.c_int)(lambda:0);wrapped=c.CFUNCTYPE(c.c_int)(lambda:801)
        obj=Observer.__new__(Observer);obj.callback_failures=[];obj.trace=[]
        obj.bindings={b'cuInit':(wrapped,actual),b'cuGetProcAddress':(wrapped,actual),b'cuGetProcAddress_v2':(actual,wrapped)}
        a=c.cast(actual,c.c_void_p).value;w=c.cast(wrapped,c.c_void_p).value
        self.assertEqual(obj._select_pointer(b'cuInit',a),w)
        self.assertEqual(obj._select_pointer(b'cuGetProcAddress',w,12000),a)
        self.assertEqual(obj._select_pointer(b'cuGetProcAddress',a,11999),w)
        self.assertIsNone(obj._select_pointer(b'cuInit',w))
        self.assertTrue(obj.callback_failures)
        self.assertIsNone(obj._select_pointer(b'cuInit',None))

    def test_presentation_records_actual_result_separately_and_preserves_null(self):
        obj=GuardedObserver.__new__(GuardedObserver);obj.sample=12000;obj.trace=[];obj.callback_failures=[]
        output=c.c_int(0);pointer=c.pointer(output)
        self.assertEqual(obj._present_version(801,pointer),0);self.assertEqual(output.value,12000)
        self.assertEqual(obj.trace,[dict(kind='intervention',symbol='cuDriverGetVersion',original_result=801,original_value=0,presented_result=0,presented_value=12000)])
        obj.trace=[]
        self.assertEqual(obj._present_version(1,None),1);self.assertEqual(obj.trace,[])
        output.value=9000
        self.assertEqual(obj._present_version(0,pointer),0);self.assertEqual(output.value,9000)
        self.assertTrue(obj.callback_failures)

    def test_faithful_mode_has_no_sample_response(self):
        obj=GuardedObserver.__new__(GuardedObserver);obj.sample=None;obj.trace=[];obj.callback_failures=[]
        output=c.c_int(0)
        self.assertEqual(obj._present_version(801,c.pointer(output)),801)
        self.assertEqual(output.value,0);self.assertEqual(obj.trace,[])

if __name__=='__main__':unittest.main()
