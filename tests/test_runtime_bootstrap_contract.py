"""Classify bootstrap requests without treating optional lookups as requirements."""
import copy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import runtime_bootstrap_contract as contract
import cupy_bootstrap_observer as observer
import run_runtime_bootstrap as runner


class ContractTests(unittest.TestCase):
    def test_changed_execution_input_prevents_child_start(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as directory:
            folder=Path(directory)
            names=['driver-target/debug/ct_cuda.dll','sdk/runtime/bin/cudart64_12.dll']
            record=dict(source_fingerprint='source',environment=str(folder/'env'),wheels=str(folder/'wheels'),
                        installed={'files':1},python_sha256='hash',artifacts={n:'hash' for n in names})
            for mutation in ['source','package','python']+names:
                def digest(path):
                    bad=(folder/'env/Scripts/python.exe' if mutation=='python' else folder/mutation)
                    return 'changed' if path.resolve()==bad.resolve() else 'hash'
                with patch.object(runner,'source_fingerprint',return_value='changed' if mutation=='source' else 'source'), \
                     patch.object(runner,'installed',return_value={} if mutation=='package' else {'files':1}), \
                     patch.object(runner,'digest',side_effect=digest),patch.object(runner.subprocess,'run') as child:
                    with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                        runner.execute_child(folder,record,('cupy','version',False),[],folder,{})
                    child.assert_not_called()

    def test_nominal_version_cannot_be_relabelled_observed(self):
        values={runner.label(c):dict(code=0,value=12090,trace=[],patches=int(c[2]),restored=True) for c in runner.CASES}
        values['native.version_null.observed'].update(code=1,value=None)
        values['native.device_count.nominal'].update(code=35,value=0)
        values['native.device_count.observed'].update(code=35,value=0,trace=[dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0)])
        self.assertEqual(runner.evaluate(values)['runtime_version'],12090)
        values['cupy.version.nominal']['patches']=1
        with self.assertRaises(ValueError):runner.evaluate(values)

    def test_native_prefix_requires_nominal_agreement_and_real_failed_call(self):
        nominal=dict(code=35,value=0,trace=[],patches=0,restored=True)
        observed=dict(nominal,trace=[dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0)],patches=1)
        self.assertTrue(contract.native_prefix(nominal,observed))
        for value in [dict(observed,code=0),dict(observed,value=1),dict(observed,trace=[]),dict(observed,restored=False)]:
            self.assertFalse(contract.native_prefix(nominal,value))
        for extra in [dict(kind='call',symbol='cuInit',result=0,flags=0),dict(kind='call',symbol='cuDriverGetVersion',result=0,value=12090)]:
            self.assertFalse(contract.native_prefix(nominal,dict(observed,trace=[extra]+observed['trace'])))
        self.assertFalse(contract.native_prefix(dict(nominal,patches=False),observed))

    def test_classification_separates_lookup_resolution_and_execution(self):
        trace=[dict(kind='lookup',symbol='cuGetProcAddress_v2',found=True),
               dict(kind='resolver_v2',symbol='cuInit',version=2000,flags=0,result=0,status=None,found=True),
               dict(kind='resolver_v2',symbol='optional',version=12000,flags=0,result=0,status=1,found=False),
               dict(kind='resolver_v1',symbol='cuLaunchKernel',version=12000,flags=2,result=801,found=False),
               dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0)]
        value=contract.classify(trace)
        self.assertEqual(value['rows'],5)
        self.assertEqual(value['resolved'],1)
        self.assertEqual(value['null_success'],1)
        self.assertEqual(value['unsupported_request'],1)
        self.assertEqual(value['failed_calls'],['cuDriverGetVersion'])
        self.assertFalse(value['mandatory_apis_established'])
        for change in ('result','flags','version'):
            bad=copy.deepcopy(trace);bad[1][change]=True
            with self.assertRaises(ValueError):contract.classify(bad)
        with self.assertRaises(ValueError):contract.classify([dict(kind='unknown')])
        for row in [dict(kind='call',symbol='cuInit',result=0,flags=-1),
                    dict(kind='call',symbol='cuDriverGetVersion',result=0,value=2**31),
                    dict(kind='resolver_v2',symbol='cuInit',version=2000,flags=0,result=0,status=0,found=None),
                    dict(kind='resolver_v2',symbol='cuInit',version=2000,flags=0,result=0,status=0,found=False)]:
            with self.subTest(row=row),self.assertRaises(ValueError):contract.classify([row])

    def test_pure_version_query_needs_constant_and_empty_trace(self):
        value=dict(code=0,value=12090,trace=[],patches=1,restored=True)
        self.assertTrue(contract.version_only(value))
        for key,bad in [('value',12000),('code',True),('restored',False),('trace',[dict(kind='call')])]:
            self.assertFalse(contract.version_only(dict(value,**{key:bad})))

    def test_native_dll_observation_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as directory:
            dll=Path(directory)/'probe.dll';dll.write_bytes(b'not-executed')
            instance=observer.Observer.__new__(observer.Observer)
            instance.saved=[];instance.restore=Mock();instance.kernel=SimpleNamespace(GetModuleHandleW=Mock(return_value=0))
            with self.assertRaises(ValueError):instance.install((SimpleNamespace(__file__=str(dll)),))
            instance.kernel.GetModuleHandleW.assert_not_called()
            with patch.object(observer,'import_slots',return_value=(4096,[])):
                with self.assertRaises(OSError):instance.install((SimpleNamespace(__file__=str(dll)),),native_probe=True)
            instance.kernel.GetModuleHandleW.assert_called_once()


if __name__=='__main__':unittest.main()
