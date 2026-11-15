import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_loader_diagnostics import mixed_runtime
from ct import inspect_pe
from triage_matrixmul import derive_diagnostic, observation_commands, validate_saved_diagnostic, recheck


class MatrixMulTriageTests(unittest.TestCase):
    def setUp(self):
        cache=Path(__file__).resolve().parents[1]/'.cache/matrixmul-triage-tests';cache.mkdir(parents=True,exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(dir=cache);self.addCleanup(self.temporary.cleanup)
        self.folder=Path(self.temporary.name);self.reference=self.folder/'reference'
        self.out=self.folder/'observations/capture';self.out.mkdir(parents=True)
        (self.folder/'keep').mkdir();(self.folder/'matrixMul.exe').write_bytes(mixed_runtime())
        (self.folder/'keep/matrixMul.ptx').write_text('.version 8.0\n.target sm_52\n.address_size 64\n.shared .align 4 .b8 tile[16];\nbar.sync 0;\n',encoding='utf-8')
        self.report=inspect_pe(mixed_runtime(),runtime=True,diagnostic=True)
        data={'inspect.stdout':json.dumps(self.report).encode(),'inspect.stderr':b'',
              'strict-inspect.stdout':json.dumps(dict(status='error',reason='unsupported static Runtime symbol')).encode(),
              'strict-inspect.stderr':b'','translate.stdout':b'',
              'translate.stderr':b'line=4 category=unsupported\n'}
        for n,b in data.items():(self.out/n).write_bytes(b)
        self.observations=dict(directory='observations/capture',commands=observation_commands(self.folder,self.reference,self.out),
                               returncodes={'inspect':0,'strict-inspect':2,'translate':3})

    def test_derives_all_fields_from_closed_observations(self):
        value=derive_diagnostic(self.folder,self.reference,self.observations)
        self.assertIs(value['application_execution_performed'],False)
        self.assertIs(value['gpu_execution_performed'],False)
        self.assertEqual(value['strict_inspect_exit'],2)
        self.assertEqual(value['offline_ptx']['first_token'],'.shared')
        self.assertEqual(value['offline_ptx']['block_barriers'],1)
        validate_saved_diagnostic(self.folder,self.reference,self.observations,value)

    def test_closed_imports_are_unproven_and_never_run(self):
        from test_ct_loader import image
        data=image(symbol=b'cudaMalloc',library=b'cudart64_12.dll')
        (self.folder/'matrixMul.exe').write_bytes(data)
        report=inspect_pe(data,runtime=True,diagnostic=True)
        (self.out/'inspect.stdout').write_text(json.dumps(report))
        (self.out/'strict-inspect.stdout').write_text(json.dumps(inspect_pe(data,runtime=True)))
        self.observations['returncodes']['strict-inspect']=0
        value=derive_diagnostic(self.folder,self.reference,self.observations)
        self.assertEqual(value['imports']['unsupported_imports'],[])
        self.assertEqual(value['imports']['compatibility'],'unproven')
        self.assertFalse(value['application_execution_performed'])
        for command in self.observations['commands'].values():
            self.assertNotIn('run',command)
            self.assertNotEqual(command[0],str(self.folder/'matrixMul.exe'))

    def test_translated_module_remains_unproven_and_never_runs(self):
        self.test_closed_imports_are_unproven_and_never_run()
        module=(Path(__file__).parent/'fixtures/vector_add.spv').read_bytes()
        (self.out/'translated.spv').write_bytes(module);(self.out/'translate.stderr').write_bytes(b'')
        self.observations['returncodes']['translate']=0
        value=derive_diagnostic(self.folder,self.reference,self.observations)
        self.assertEqual(value['offline_ptx']['status'],'translated')
        self.assertEqual(value['offline_ptx']['validation'],'not_run')
        self.assertGreater(value['offline_ptx']['entry_count'],0)
        self.assertFalse(value['application_execution_performed']);self.assertFalse(value['gpu_execution_performed'])
        validate_saved_diagnostic(self.folder,self.reference,self.observations,value)
        (self.out/'translated.spv').write_bytes(b'not SPIR-V')
        with self.assertRaises(ValueError):derive_diagnostic(self.folder,self.reference,self.observations)

    def test_saved_execution_flags_and_nested_values_cannot_be_relabelled(self):
        original=derive_diagnostic(self.folder,self.reference,self.observations)
        for mutation in ('app','app_zero','gpu','exit','token','extra','bool_count'):
            v=copy.deepcopy(original)
            if mutation=='app':v['application_execution_performed']=True
            if mutation=='app_zero':v['application_execution_performed']=0
            if mutation=='gpu':v['gpu_execution_performed']=True
            if mutation=='exit':v['strict_inspect_exit']=0
            if mutation=='token':v['offline_ptx']['first_token']='ret;'
            if mutation=='extra':v['extra']=0
            if mutation=='bool_count':v['offline_ptx']['block_barriers']=True
            with self.assertRaises(ValueError):validate_saved_diagnostic(self.folder,self.reference,self.observations,v)

    def test_invalid_commands_exit_types_and_raw_outputs_rejected(self):
        for mutation in ('command','exit','bool_exit','translate_exit','escape'):
            v=copy.deepcopy(self.observations)
            if mutation=='command':v['commands']['strict-inspect']=['fake']
            if mutation=='exit':v['returncodes']['strict-inspect']=0
            if mutation=='bool_exit':v['returncodes']['inspect']=False
            if mutation=='translate_exit':v['returncodes']['translate']=1
            if mutation=='escape':v['directory']='../outside'
            with self.assertRaises(ValueError):derive_diagnostic(self.folder,self.reference,v)
        (self.out/'translate.stderr').write_bytes(b'line 9999: invalid\n')
        with self.assertRaises(ValueError):derive_diagnostic(self.folder,self.reference,self.observations)

    def test_recheck_normalizes_relative_manifest_before_observation(self):
        path=self.folder/'manifest.json';path.write_text('{}',encoding='utf-8')
        relative=path.relative_to(Path(__file__).resolve().parents[1])
        diagnostic=derive_diagnostic(self.folder,self.reference,self.observations)
        value=dict(files={},reference={'files':{}},source_fingerprint='same',diagnostic=diagnostic)
        with patch('triage_matrixmul.audit',return_value=(value,self.reference)), \
             patch('triage_matrixmul.inspect_capture',return_value=(diagnostic,self.observations)) as inspect, \
             patch('triage_matrixmul.verify_files'),patch('triage_matrixmul.source_fingerprint',return_value='same'), \
             patch('triage_matrixmul.observation_files',return_value={}):
            recheck(relative)
        inspect.assert_called_once_with(self.folder,self.reference,{})


if __name__=='__main__':unittest.main()
