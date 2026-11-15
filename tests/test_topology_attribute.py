import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
try:check=importlib.import_module('topology_attribute_check')
except ModuleNotFoundError as error:
    if error.name!='topology_attribute_check':raise
    check=None


def fixture(virtual=True):
    return dict(status='pass',virtual=virtual,device_name='Intel synthetic',max_slices=2,max_subslices_per_slice=6,topology_count=12,
                driver_code=0 if virtual else 801,driver_value=12 if virtual else 0,
                runtime_code=0 if virtual else 801,runtime_value=12 if virtual else 456,
                identity_unique=True,snapshot_stable=True,context_unchanged=True,policy_immutable=True,
                physical_intel=True,maxima_only=True,nvidia_sm_claim=False)


class TopologyOracleTests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(check,'topology oracle not implemented')

    def test_both_apis_require_independent_checked_maximum_topology(self):
        for mode in ('virtual_rt_first','virtual_driver_first','minimal_virtual'):
            self.assertTrue(check.topology_valid(mode,fixture()))
        for mode in ('strict_rt_first','strict_driver_first','minimal_strict'):
            self.assertTrue(check.topology_valid(mode,fixture(False)))
        for key,bad in (('max_slices',0),('max_subslices_per_slice',True),('topology_count',13),('driver_value',True),
                        ('runtime_value',1),('identity_unique',False),('snapshot_stable',False),('nvidia_sm_claim',True),('maxima_only',False)):
            self.assertFalse(check.topology_valid('virtual_rt_first',dict(fixture(),**{key:bad})))
        self.assertFalse(check.topology_valid('strict_rt_first',fixture()))

    def test_native_maximum_must_fit_without_clamping(self):
        for slices,subslices in ((0,1),(1,0),(1,2**31),(2**32-1,2),(2**32,1)):
            value=fixture();value.update(max_slices=slices,max_subslices_per_slice=subslices,topology_count=slices*subslices,
                                         driver_value=slices*subslices,runtime_value=slices*subslices)
            self.assertFalse(check.topology_valid('virtual_rt_first',value))

    def test_loader_failures_are_not_metadata_success(self):
        for mode in ('missing','forwarded','absent'):
            self.assertTrue(check.topology_valid(mode,dict(status='pass',loader_error=35)))
            self.assertFalse(check.topology_valid(mode,dict(status='pass',loader_error=801)))
        self.assertFalse(check.topology_valid('unknown',fixture()))

    def test_profile_declares_maxima_semantics_and_strict_refusal(self):
        import run_virtual_target
        self.assertEqual(run_virtual_target.profile()['topology_count'],check.TOPOLOGY_POLICY)


class TopologyHistoryTests(unittest.TestCase):
    def test_historical_r2t_refuses_before_any_budget_or_native_work(self):
        import run_runtime_scheduling as runner
        with patch.object(runner,'source_fingerprint',return_value='new-source',create=True), \
             patch.object(runner,'ensure_budget') as budget, \
             patch.object(runner,'parent_capture',side_effect=AssertionError('native started')) as parent:
            with self.assertRaisesRegex(ValueError,'historical R2t'):runner.capture(Path('unused'),Path('unused'))
            budget.assert_not_called();parent.assert_not_called()


class TopologyRunnerTests(unittest.TestCase):
    def setUp(self):
        try:self.runner=importlib.import_module('run_topology_attribute')
        except ModuleNotFoundError as error:
            if error.name!='run_topology_attribute':raise
            self.fail('topology runner not implemented')

    def test_budget_refuses_before_parent_output(self):
        with patch.object(self.runner,'ensure_budget',side_effect=ValueError('cache_limit')),patch.object(self.runner,'parent_capture') as parent:
            with self.assertRaisesRegex(ValueError,'cache_limit'):self.runner.build()
            parent.assert_not_called()

    def test_saved_child_requires_runtime_and_binds_its_role(self):
        runner=self.runner
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            folder=Path(name);bundle=folder/'topology/virtual_rt_first';bundle.mkdir(parents=True)
            files={}
            for n in ('topology.exe','ct_cudart.dll','ct_cuda.dll'):
                (folder/n).write_bytes(n.encode());files[n]=runner.digest(folder/n)
            wanted=runner.payloads(files,'topology','virtual_rt_first')
            for n in wanted:(bundle/n).write_bytes((folder/('topology.exe' if n=='consumer.exe' else 'ct_cudart.dll' if n=='cudart64_12.dll' else 'ct_cuda.dll')).read_bytes())
            (bundle/'stdout.json').write_text(json.dumps(fixture()));(bundle/'stderr.txt').write_bytes(b'')
            row=dict(mode='virtual_rt_first',files=wanted,exit_code=0,observations={n:runner.digest(bundle/n) for n in ('stdout.json','stderr.txt')})
            self.assertTrue(runner.validate_row(folder,files,row,'topology','virtual_rt_first'))
            (bundle/'cudart64_12.dll').unlink()
            with self.assertRaises(ValueError):runner.validate_row(folder,files,row,'topology','virtual_rt_first')
            (bundle/'cudart64_12.dll').write_bytes(b'wrong runtime')
            with self.assertRaises(ValueError):runner.validate_row(folder,files,row,'topology','virtual_rt_first')

    def test_parent_role_cannot_be_substituted_even_with_matching_hash(self):
        runner=self.runner
        self.assertTrue(hasattr(runner,'validate_parent_identity'),'parent role gate not implemented')
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            path=Path(name)/'manifest.json'
            parent=dict(scope='diagnostic_runtime_attribute',source_fingerprint='source',release_claim=False)
            path.write_text(json.dumps(parent));record=dict(source_fingerprint='source',parent_manifest_sha256=runner.digest(path))
            runner.validate_parent_identity(path,parent,record)
            parent['scope']='different_diagnostic';path.write_text(json.dumps(parent));record['parent_manifest_sha256']=runner.digest(path)
            with self.assertRaises(ValueError):runner.validate_parent_identity(path,parent,record)
