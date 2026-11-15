"""Synthetic peer evidence cannot become CT/device/application support."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import bootstrap_peer_check as check
import run_bootstrap_peer as runner

def row(kind,symbol,result=801,value=0):
    return dict(kind=kind,symbol=symbol,version=0,flags=0,result=result,status=-1,found=0,value=value,uuid='0'*32)

def trial(mode,enabled=True):
    code,value=check.RESPONSES[mode]
    calls=[row(5,'cuGetExportTable'),row(3,'cuDriverGetVersion',code,value)]
    if mode>=3:calls.append(row(4,'cuInit'))
    return dict(scope='synthetic_intervention',application_supported=False,mode=mode,trace_enabled=enabled,
                outcome=dict(status='returned',code=35 if mode<3 else 801,count=-1),
                trace=calls if enabled else [],overflow=False,provider_sha256='a'*64,runtime_sha256='b'*64)

class PeerEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (Path(__file__).resolve().parents[1]/'.cache').mkdir(exist_ok=True)

    def test_debug_symbol_annotation_is_not_a_forwarded_export(self):
        for suffix in ('',' = cuInit'):
            self.assertEqual(runner.export_names(' 1 0 00002FD0 cuInit'+suffix),{'cuInit'})
        for text in (' 1 0 00002FD0 cuInit = other.dll.cuInit',' 1 0 cuInit (forwarded to other.cuInit)'):
            with self.assertRaises(ValueError):runner.export_names(text)
    def test_peer_inventory_rejects_backend_or_launch_surface(self):
        names=set(runner.EXPORTS)
        runner.inventory(names,['KERNEL32.dll','ntdll.dll'])
        for bad in [names|{'cuLaunchKernel'},names-{'cuInit'}]:
            with self.assertRaises(ValueError):runner.inventory(bad,['KERNEL32.dll'])
        with self.assertRaises(ValueError):runner.inventory(names,['ze_loader.dll'])
        with self.assertRaises(ValueError):runner.inventory(names,['ct_cuda.dll'])

    def test_input_mutation_stops_child_before_execution(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root/'.cache') as directory:
            folder=Path(directory);record=dict(source_fingerprint='s',python=str(folder/'python.exe'),python_sha256='h',artifacts={'peer.dll':'h'})
            with patch.object(runner,'source_fingerprint',return_value='s'),patch.object(runner,'digest',return_value='changed'),patch.object(runner.subprocess,'run') as child:
                with self.assertRaises(ValueError):runner.execute(folder,record,[],folder,{})
                child.assert_not_called()
    def test_version_progress_is_synthetic_and_does_not_imply_compatibility(self):
        for mode in range(5):
            result=check.validate_trial(trial(mode))
            self.assertFalse(result['application_supported'])
            self.assertEqual(result['init_attempted'],mode>=3)
            self.assertFalse(result['ct_compatibility_inferred'])

    def test_advanced_or_native_fault_outcomes_are_rejected(self):
        for status,code in [('returned',0),('native_fault',None)]:
            value=trial(3);value['outcome'].update(status=status,code=code)
            with self.assertRaises(ValueError):check.validate_trial(value)

    def test_false_claim_or_unexpected_calls_cannot_pass(self):
        for key,value in [('scope','nominal_ct'),('application_supported',True),('overflow',True),('mode',True)]:
            changed=trial(3);changed[key]=value
            with self.assertRaises(ValueError):check.validate_trial(changed)
        for changed in [row(4,'cuInit',0),row(6,'cuLaunchKernel',801),row(5,'cuGetExportTable',0)]:
            value=trial(3);value['trace'].append(changed)
            with self.assertRaises(ValueError):check.validate_trial(value)

    def test_trace_mode_and_response_cannot_be_relabelled(self):
        value=trial(3);value['trace'][1]['value']=12090
        with self.assertRaises(ValueError):check.validate_trial(value)
        with self.assertRaises(ValueError):check.validate_trial(dict(trial(3),trace_enabled=False))
        value=trial(3);value['trace'][2]['flags']=-1
        with self.assertRaises(ValueError):check.validate_trial(value)

    def test_tracing_off_comparison_matches_outcome_without_claiming_calls(self):
        result=check.compare_pair(trial(3),trial(3,False))
        self.assertEqual(result['observed_call_order'],['cuGetExportTable','cuDriverGetVersion','cuInit'])
        self.assertTrue(result['tracing_control_matches'])
        bad=trial(3,False);bad['outcome']['code']=35
        with self.assertRaises(ValueError):check.compare_pair(trial(3),bad)

if __name__=='__main__':unittest.main()
