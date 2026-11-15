import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from test_runtime_virtual_metadata import fixture as previous_fixture
try:
    check=importlib.import_module('runtime_topology_check')
    observer=importlib.import_module('runtime_topology_observer')
except ModuleNotFoundError as error:
    if error.name not in ('runtime_topology_check','runtime_topology_observer'):raise
    check=observer=None


def fixture():
    value=previous_fixture();value['scope']='ct_topology_metadata_prefix'
    value['prefix_trace']=value['prefix_trace'][:2]+check.expected_prefix(12000,'Intel synthetic',8192,13,12)
    value['scheduling_controls']=[dict(attribute=a,ordinal=0,result=0,value=0) for a in (15,40)]
    value['topology_control']=dict(attribute=16,ordinal=0,result=0,value=12)
    value['boundary_control']=dict(attribute=13,ordinal=0,result=801,value=0)
    return value


class TopologyTests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(check,'topology prefix is not implemented')

    def test_actual_boundary_after_successful_overlap(self):
        result=check.validate(fixture())
        self.assertEqual(result['actual_attribute'],13)
        self.assertEqual(result['actual_attribute_code'],801)
        self.assertEqual(result['actual_overlap'],0)
        self.assertFalse(result['application_supported'])

    def test_observed_async_engine_step_is_required(self):
        rows=[r for r in fixture()['prefix_trace'] if r.get('kind','').startswith('scheduling_attribute')]
        self.assertEqual([r['attribute'] for r in rows],[75,76,15,40,16,13])

    def test_boundary_is_observed_not_fixed_to_a_guessed_enum(self):
        value=fixture();value['boundary_control']['attribute']=14
        value['prefix_trace'][-1]['attribute']=14
        self.assertEqual(check.validate(value)['actual_attribute'],14)
        for bad in (True,0,-1,256,15,16,40,75,1):
            changed=copy.deepcopy(value);changed['boundary_control']['attribute']=bad;changed['prefix_trace'][-1]['attribute']=bad
            with self.assertRaises(ValueError):check.validate(changed)

    def test_topology_count_is_positive_exact_and_matches_actual_trace(self):
        for bad in (True,0,-1,2**31,13):
            value=fixture();value['topology_control']['value']=bad
            with self.assertRaises(ValueError):check.validate(value)
        value=fixture();value['topology_control']['value']=24
        value['prefix_trace'][-2]['value']=24
        self.assertEqual(check.validate(value)['actual_topology_count'],24)

    def test_exact_order_native_values_and_types(self):
        value=fixture()
        for offset,key,bad in ((-6,'attribute',76),(-6,'value',6),(-4,'value',True),(-3,'result',801),(-3,'value',1),(-2,'value',1),(-1,'result',0),(-1,'ordinal',True)):
            changed=copy.deepcopy(value);changed['prefix_trace'][offset][key]=bad
            with self.assertRaises(ValueError):check.validate(changed)
        for trace in (value['prefix_trace'][:-1],value['prefix_trace']+[value['prefix_trace'][-1]]):
            with self.assertRaises(ValueError):check.validate(dict(value,prefix_trace=trace))

    def test_direct_controls_and_state_are_required(self):
        value=fixture()
        for key,field,bad in (('boundary_control','attribute',14),('boundary_control','result',0),('boundary_control','value',True),('native_prefix','calls',2),('primary_after_reset','active',1)):
            changed=copy.deepcopy(value);changed[key][field]=bad
            with self.assertRaises(ValueError):check.validate(changed)
        for index in (0,1):
            for bad in (True,1,-1):
                changed=copy.deepcopy(value);changed['scheduling_controls'][index]['value']=bad
                with self.assertRaises(ValueError):check.validate(changed)
        for key,bad in (('policy_mode','strict-default'),('software_target_only',False),('application_supported',True)):
            with self.assertRaises(ValueError):check.validate(dict(value,**{key:bad}))

    def test_observer_checks_order_phase_and_native_state_before_query(self):
        import ctypes as c
        obj=observer.TopologyObserver.__new__(observer.TopologyObserver)
        obj.topology_count=12;obj.phase=3;obj.metadata_step=2;obj.callback_failures=[];obj.trace=[];obj.owner=Mock()
        obj.owner.native_state.return_value=dict(calls=1,result=0,nonnull=1)
        output=c.pointer(c.c_int())
        self.assertTrue(obj._scheduling_ready(output,75,0))
        self.assertFalse(obj._scheduling_ready(output,76,0))
        obj.metadata_step=5
        self.assertTrue(obj._scheduling_ready(output,40,0))
        self.assertFalse(obj._scheduling_ready(output,16,0))
        obj.metadata_step=6
        self.assertTrue(obj._scheduling_ready(output,16,0))
        self.assertFalse(obj._scheduling_ready(output,13,0))
        obj.metadata_step=7
        self.assertTrue(obj._scheduling_ready(output,13,0))
        self.assertFalse(obj._scheduling_ready(output,16,0))
        obj.phase=2
        self.assertFalse(obj._scheduling_ready(output,16,0))

    def test_unwrapped_native_addresses_cannot_escape_the_latch(self):
        obj=observer.TopologyObserver.__new__(observer.TopologyObserver)
        obj.bindings={};obj.callback_failures=[];obj.trace=[]
        for symbol in (b'cuUnreviewedOperation',b'cuUnknownAllocation'):
            self.assertIsNone(obj._select_pointer(symbol,12345))
        self.assertTrue(obj.callback_failures)
        self.assertIsNone(obj._select_pointer(b'unknown',None))

    def test_cached_wrapped_callback_stops_after_boundary(self):
        import ctypes as c
        obj=observer.TopologyObserver.__new__(observer.TopologyObserver)
        obj.phase=3;obj.boundary_seen=False;obj.callback_failures=[];obj.guard_hits=[];obj.blocked_callbacks=[];obj.trace=[]
        obj.owner=Mock();obj.owner.state.return_value=dict(mask=0,stopped=0,reserved=0)
        obj.owner.native_state.return_value=dict(calls=1,result=0,nonnull=1)
        actual=Mock(return_value=0);signature=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_int))
        cached=obj._callback('cached_scheduling',signature,actual,clear_output=0)
        obj.boundary_seen=True;out=c.c_int(123)
        self.assertEqual(cached(c.byref(out)),999);self.assertEqual(out.value,0)
        actual.assert_not_called()

    def test_saved_trace_rejects_unwrapped_success_and_post_unload_context(self):
        value=fixture()
        for bad in (None,{},dict(code=0,is_null=False),dict(code=True,is_null=True)):
            with self.assertRaises(ValueError):check.validate(dict(value,context_after=bad))
        row=dict(kind='lookup',symbol='cuCtxSetCurrent',found=True)
        changed=copy.deepcopy(value);changed['prefix_trace'].insert(2,row)
        with self.assertRaises(ValueError):check.validate(changed)

    def test_known_nonforwarded_lookup_returns_typed_deny_callback(self):
        import ctypes as c
        obj=observer.TopologyObserver.__new__(observer.TopologyObserver)
        obj.phase=3;obj.boundary_seen=False;obj.callback_failures=[];obj.guard_hits=[];obj.blocked_callbacks=[];obj.trace=[];obj.callbacks=[];obj.bindings={}
        obj.owner=Mock();obj.owner.state.return_value=dict(mask=0,stopped=0,reserved=0)
        obj.owner.native_state.return_value=dict(calls=1,result=0,nonnull=1)
        actual_call=Mock(return_value=0);signature=c.WINFUNCTYPE(c.c_int,c.c_void_p)
        actual=signature(actual_call);pointer=c.cast(actual,c.c_void_p).value
        guarded=obj._select_pointer(b'cuCtxSetCurrent',pointer)
        self.assertTrue(guarded);self.assertNotEqual(guarded,pointer)
        self.assertEqual(signature(guarded)(None),801);actual_call.assert_not_called()
        self.assertEqual(obj.guard_hits[0]['symbol'],'cuCtxSetCurrent')

    def test_saved_guard_binding_is_required_for_each_known_extra_lookup(self):
        value=fixture();lookup=dict(kind='lookup',symbol='cuCtxSetCurrent',found=True)
        value['prefix_trace'][2:2]=[lookup,dict(kind='scheduling_guard_binding',symbol='cuCtxSetCurrent')]
        self.assertEqual(check.validate(value)['actual_attribute'],13)
        changed=copy.deepcopy(value);changed['prefix_trace'].insert(3,dict(lookup))
        with self.assertRaises(ValueError):check.validate(changed)
        changed=copy.deepcopy(value);changed['prefix_trace'].pop(3)
        with self.assertRaises(ValueError):check.validate(changed)


class TopologyRunnerTests(unittest.TestCase):
    def setUp(self):
        try:self.runner=importlib.import_module('run_runtime_topology')
        except ModuleNotFoundError as error:
            if error.name!='run_runtime_topology':raise
            self.fail('scheduling runner is not implemented')

    def test_insufficient_space_stops_before_parent_capture(self):
        with patch.object(self.runner,'source_fingerprint',return_value='unused',create=True), \
             patch.object(self.runner,'ensure_budget',side_effect=ValueError('cache_limit')),patch.object(self.runner,'parent_capture') as parent:
            with self.assertRaisesRegex(ValueError,'cache_limit'):self.runner.capture(Path('python'),Path('runtime.zip'))
            parent.assert_not_called()

    def test_required_runtime_identity_and_sample_role(self):
        runner=self.runner
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            folder=Path(name);bundle=folder/'sample';bundle.mkdir();(bundle/'nvcuda.dll').write_bytes(b'provider')
            direct=folder/'direct';direct.mkdir();(direct/'stdout.json').write_text(json.dumps({'result':{'device_name':'Intel synthetic'}}))
            sha=runner.digest(bundle/'nvcuda.dll');build={'files':{'context-bridge/bridge.dll':sha}}
            base={'artifacts':{'sdk/'+runner.SDK+'/bin/cudart64_12.dll':'f'*64}}
            value=fixture();value.update(provider_sha256=sha,runtime_sha256=None)
            with self.assertRaises(ValueError):runner.validate_child(folder,bundle,build,base,'intervention',value)
            runtime=bundle/'cudart64_12.dll';runtime.write_bytes(b'runtime');expected=runner.digest(runtime)
            base['artifacts']['sdk/'+runner.SDK+'/bin/cudart64_12.dll']=expected
            for reported in (None,'e'*64):
                value['runtime_sha256']=reported
                with self.assertRaises(ValueError):runner.validate_child(folder,bundle,build,base,'intervention',value)
            value['runtime_sha256']=expected
            self.assertEqual(runner.validate_child(folder,bundle,build,base,'intervention',value)['actual_attribute'],13)
            with self.assertRaises(ValueError):runner.validate_child(folder,bundle,build,base,'intervention12090',value)

    def test_parent_path_and_hash_are_bound_before_native_audit(self):
        runner=self.runner
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache/runtime-attribute-runs') as name:
            path=Path(name)/'topology-manifest.json';path.write_text(json.dumps({'summary':{'topology_count':12}}))
            record=dict(topology_parent=str(path.relative_to(ROOT)),topology_parent_sha256=runner.digest(path))
            with patch.object(runner,'topology_audit',return_value={'topology_count':12}) as audit:
                self.assertEqual(runner.validate_topology_parent(record),{'topology_count':12})
                for bad in ('../outside/topology-manifest.json','docs/topology-manifest.json'):
                    with self.assertRaises(ValueError):runner.validate_topology_parent(dict(record,topology_parent=bad))
                for bad in ('f'*64,None):
                    with self.assertRaises(ValueError):runner.validate_topology_parent(dict(record,topology_parent_sha256=bad))
                self.assertEqual(audit.call_count,1)
            with patch.object(runner,'topology_audit',return_value={'topology_count':13}):
                with self.assertRaises(ValueError):runner.validate_topology_parent(record)

    def test_strict_control_refuses_runtime_presence_or_identity(self):
        runner=self.runner
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            bundle=Path(name);(bundle/'nvcuda.dll').write_bytes(b'provider')
            sha=runner.digest(bundle/'nvcuda.dll');build={'files':{'context-bridge/bridge.dll':sha}}
            for present,reported in ((False,'f'*64),(True,None)):
                if present:(bundle/'cudart64_12.dll').write_bytes(b'runtime')
                value=dict(provider_sha256=sha,runtime_sha256=reported)
                with self.assertRaises(ValueError):runner.validate_child(bundle,bundle,build,{},'strict-control',value)
