import copy
import ctypes as c
import importlib
from pathlib import Path
import sys
import json
import tempfile
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
try:
    check=importlib.import_module('runtime_virtual_metadata_check')
    observer=importlib.import_module('runtime_virtual_metadata_observer')
    runner=importlib.import_module('run_runtime_virtual_metadata')
except ModuleNotFoundError as error:
    if error.name not in ('runtime_virtual_metadata_check','runtime_virtual_metadata_observer','run_runtime_virtual_metadata'):raise
    check=observer=runner=None


def fixture():
    lookup=dict(kind='resolver_v2',symbol='cuGetExportTable',version=3000,flags=0,result=0,status=None,found=False)
    surface=dict(kind='export_surface_intervention',symbol='cuGetExportTable',version=3000,flags=0,original_result=0,original_found=False,
                 original_status=None,presented_result=0,presented_found=True,presented_status=None)
    return dict(scope='ct_virtual_metadata_prefix',sample=12000,application_supported=False,shipping_version_authorized=False,
                state_failures=[],foreign_lookups=[],policy_mode='ct-sm52-subset-v1',policy_env_value='ct-sm52-subset-v1',software_target_only=True,
                name_control=dict(code=0,value='Intel synthetic'),memory_control=dict(code=0,total_bytes=8192),
                actual_version_before=dict(code=801,value=0),actual_version_after=dict(code=801,value=0),result=dict(status='returned',code=3,value=-1),
                prefix_trace=[lookup,surface]+check.expected_prefix(12000,'Intel synthetic',8192),teardown_trace=[],guard_hits=[],callback_failures=[],blocked_callbacks=[],
                restored=True,patches=1,restore_error=None,runtime_unload=dict(free_succeeded=True,module_absent=True),context_after=dict(code=0,is_null=True),
                deny_before=dict(mask=0,stopped=0,reserved=0),deny_prefix=dict(mask=0,stopped=0,reserved=0),deny_after_runtime=dict(mask=0,stopped=0,reserved=0),
                native_before=dict(calls=0,result=0,nonnull=0),native_prefix=dict(calls=1,result=0,nonnull=1),native_after_runtime=dict(calls=1,result=0,nonnull=1),
                primary_before_reset=dict(code=0,flags=0,active=0),primary_reset_code=0,primary_after_reset=dict(code=0,flags=0,active=0),current_after_reset=dict(code=0,is_null=True))


class VirtualMetadataTests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(check,'virtual metadata profile is not implemented')

    def test_actual_virtual_policy_attributes_stop_at_fifteen(self):
        value=fixture();result=check.validate(value)
        self.assertEqual(result['actual_attribute'],15)
        self.assertEqual(result['actual_attribute_code'],801)
        self.assertFalse(result['application_supported'])
        self.assertEqual(result['virtual_major_minor'],[5,2])

    def test_order_values_and_native_scalar_types_are_fixed(self):
        value=fixture()
        for offset,key,bad in ((-3,'attribute',76),(-3,'value',6),(-2,'value',True),(-1,'result',0),(-1,'value',1),(-1,'attribute',40)):
            changed=copy.deepcopy(value);changed['prefix_trace'][offset][key]=bad
            with self.assertRaises(ValueError):check.validate(changed)
        for trace in (value['prefix_trace'][:-1],value['prefix_trace']+[value['prefix_trace'][-1]]):
            changed=copy.deepcopy(value);changed['prefix_trace']=trace
            with self.assertRaises(ValueError):check.validate(changed)

    def test_policy_hardware_claim_and_callback_state_cannot_be_substituted(self):
        value=fixture()
        for key,bad in (('policy_mode','strict-default'),('policy_env_value',None),('software_target_only',False),('shipping_version_authorized',True)):
            changed=copy.deepcopy(value);changed[key]=bad
            with self.assertRaises(ValueError):check.validate(changed)
        for key,field,bad in (('memory_control','total_bytes',8193),('native_prefix','calls',2),('primary_after_reset','active',1)):
            changed=copy.deepcopy(value);changed[key][field]=bad
            with self.assertRaises(ValueError):check.validate(changed)

    def test_actual_strict_post_control_is_required(self):
        value=dict(scope='ct_virtual_metadata_strict_control',policy_env_absent=True,init_code=0,
                   device_count=dict(code=0,value=1),attribute=dict(attribute=75,ordinal=0,result=801,value=0),
                   actual_version=dict(code=801,value=0),primary_state=dict(code=0,flags=0,active=0),current=dict(code=0,is_null=True),
                   application_supported=False,shipping_version_authorized=False)
        check.validate_strict_control(value)
        for key,field,bad in (('attribute','value',5),('attribute','result',0),('attribute','attribute',76),('attribute','ordinal',True),('primary_state','active',1)):
            changed=copy.deepcopy(value);changed[key][field]=bad
            with self.assertRaises(ValueError):check.validate_strict_control(changed)
        changed=copy.deepcopy(value);changed['policy_env_absent']=False
        with self.assertRaises(ValueError):check.validate_strict_control(changed)

    def test_observer_rejects_wrong_attribute_before_forwarding(self):
        obj=observer.VirtualMetadataObserver.__new__(observer.VirtualMetadataObserver)
        obj.metadata_step=2;obj.phase=3;obj.trace=[];obj.callback_failures=[];obj.owner=Mock()
        obj.owner.native_state.return_value=dict(calls=1,result=0,nonnull=1)
        output=c.pointer(c.c_int())
        self.assertTrue(obj._virtual_ready(output,75,0))
        self.assertFalse(obj._virtual_ready(output,76,0));self.assertTrue(obj.callback_failures)

    def test_insufficient_space_stops_before_parent_capture(self):
        with patch.object(runner,'source_fingerprint',return_value='efd1956be57db50e68a10ec379d990d171f246e7247eac213d839d4be5744f2c',create=True), \
             patch.object(runner,'ensure_budget',side_effect=ValueError('cache_limit')),patch.object(runner,'parent_capture') as parent:
            with self.assertRaisesRegex(ValueError,'cache_limit'):runner.capture(Path('python'),Path('runtime.zip'))
            parent.assert_not_called()

    def test_saved_virtual_sample_requires_runtime_file_and_reported_identity(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            folder=Path(name);bundle=folder/'sample';bundle.mkdir();(bundle/'nvcuda.dll').write_bytes(b'provider')
            direct=folder/'direct';direct.mkdir();(direct/'stdout.json').write_text(json.dumps({'result':{'device_name':'Intel synthetic'}}))
            provider_sha=runner.digest(bundle/'nvcuda.dll')
            build={'files':{'context-bridge/bridge.dll':provider_sha}}
            base={'artifacts':{'sdk/'+runner.SDK+'/bin/cudart64_12.dll':'f'*64}}
            value=fixture();value.update(provider_sha256=provider_sha,runtime_sha256=None)
            with self.assertRaises(ValueError):runner.validate_child(folder,bundle,build,base,'intervention',value)
            runtime=bundle/'cudart64_12.dll';runtime.write_bytes(b'runtime')
            expected=runner.digest(runtime);base['artifacts']['sdk/'+runner.SDK+'/bin/cudart64_12.dll']=expected
            for reported in (None,'e'*64):
                value['runtime_sha256']=reported
                with self.assertRaises(ValueError):runner.validate_child(folder,bundle,build,base,'intervention',value)
            value['runtime_sha256']=expected
            self.assertEqual(runner.validate_child(folder,bundle,build,base,'intervention',value)['actual_attribute'],15)

    def test_saved_strict_control_refuses_runtime_presence_or_hash(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            folder=Path(name);bundle=folder/'strict';bundle.mkdir();(bundle/'nvcuda.dll').write_bytes(b'provider')
            provider_sha=runner.digest(bundle/'nvcuda.dll');runtime=bundle/'cudart64_12.dll'
            build={'files':{'context-bridge/bridge.dll':provider_sha}}
            value=dict(scope='ct_virtual_metadata_strict_control',policy_env_absent=True,init_code=0,
                       device_count=dict(code=0,value=1),attribute=dict(attribute=75,ordinal=0,result=801,value=0),
                       actual_version=dict(code=801,value=0),primary_state=dict(code=0,flags=0,active=0),current=dict(code=0,is_null=True),
                       application_supported=False,shipping_version_authorized=False,provider_sha256=provider_sha,runtime_sha256='f'*64)
            base={'artifacts':{'sdk/'+runner.SDK+'/bin/cudart64_12.dll':'f'*64}}
            with self.assertRaises(ValueError):runner.validate_child(folder,bundle,build,base,'strict-control',value)
            runtime.write_bytes(b'runtime');value['runtime_sha256']=runner.digest(runtime);base['artifacts']['sdk/'+runner.SDK+'/bin/cudart64_12.dll']=value['runtime_sha256']
            with self.assertRaises(ValueError):runner.validate_child(folder,bundle,build,base,'strict-control',value)


if __name__=='__main__':unittest.main()
