import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from virtual_target_check import abi_valid,qualification_valid,QUALIFICATION,trace_valid,app_valid
import struct
import json
import tempfile
from matrix_runtime_check import expected_output
from run_virtual_target import check_app,app_payloads,argv_for,TARGET
from run_relaxed_nvcc import digest

class VirtualTargetTests(unittest.TestCase):
    def test_native_abi_report_is_closed_and_mode_bound(self):
        value=dict(status='pass',virtual=True,major=5,minor=2,context_unchanged=True,
                   physical_intel=True,policy_immutable=True,late_unsupported_rejected=True)
        for mode in ('virtual_rt_first','virtual_driver_first','flags'):
            self.assertTrue(abi_valid(mode,value))
        for key in value:
            bad=copy.deepcopy(value);bad[key]=None
            self.assertFalse(abi_valid('virtual_rt_first',bad))
        self.assertFalse(abi_valid('strict_rt_first',value))
        strict=dict(value,virtual=False,major=0,minor=0,late_unsupported_rejected=False)
        self.assertTrue(abi_valid('strict_rt_first',strict))
        for mode in ('invalid','empty','nonunicode'):
            self.assertTrue(abi_valid(mode,dict(status='pass',invalid_config=1)))
            self.assertFalse(abi_valid(mode,dict(status='pass',invalid_config=True)))
        self.assertTrue(abi_valid('loader',dict(status='pass',loader_error=35)))
        self.assertFalse(abi_valid('loader',dict(status='pass',loader_error=801)))

    def test_qualification_cannot_become_hardware_or_release_claim(self):
        self.assertTrue(qualification_valid(QUALIFICATION))
        for key in QUALIFICATION:
            bad=copy.deepcopy(QUALIFICATION);bad[key]=None
            self.assertFalse(qualification_valid(bad))

    def test_product_trace_never_accepts_metadata_injection(self):
        value=dict(allocations=3,h2d=2,dtoh=1,launches=301,forwarded=301,frees=3,uploaded=2,metadata_injected=False)
        self.assertTrue(trace_valid(value,'trace'))
        self.assertFalse(trace_valid(dict(value,metadata_injected=True),'trace'))
        self.assertTrue(trace_valid(dict(value,forwarded=0),'noop_launch'))
        self.assertTrue(trace_valid(dict(value,uploaded=0),'noop_copy'))
        self.assertFalse(trace_valid(value,'noop_launch'))

    def test_app_oracle_rejects_false_pass_and_bad_scope(self):
        shape=(32,32,32);a=struct.pack('<f',1.0)*1024;b=struct.pack('<f',0.01)*1024;c=expected_output(shape)
        trace=dict(allocations=3,h2d=2,dtoh=1,launches=301,forwarded=301,frees=3,uploaded=2,metadata_injected=False)
        args=(shape,0,b'Result = PASS',b'',a,b,c,trace)
        self.assertTrue(app_valid('trace',*args))
        poison=struct.pack('<I',0x7fc00000)*1024
        self.assertFalse(app_valid('trace',shape,0,b'Result = PASS',b'',a,b,poison,trace))
        self.assertTrue(app_valid('noop_launch',shape,0,b'Result = PASS',b'',a,b,poison,dict(trace,forwarded=0)))
        self.assertFalse(app_valid('noop_launch',*args))
        self.assertFalse(app_valid('trace',shape,False,b'Result = PASS',b'',a,b,c,trace))
        self.assertFalse(app_valid('trace',shape,0,b'Result = PASS',b'',a,b,c,dict(trace,metadata_injected=True)))

    def test_app_audit_binds_environment_providers_command_and_raw_outputs(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root/'.cache') as temp:
            folder=Path(temp).resolve();self.assertTrue(folder.is_relative_to(root/'.cache'))
            bundle=folder/'virtual-app-runs/capture';bundle.mkdir(parents=True)
            source={'matrixMul.exe':'matrixMul.exe','cudart64_12.dll':'matrix-runtime-original.dll','nvcuda.dll':'virtual-trace.dll','ct_underlying.dll':'ct_cuda.dll'}
            files={}
            for name in source.values():
                (folder/name).write_bytes(name.encode());files[name]=digest(folder/name)
            for dst,src in source.items():(bundle/dst).write_bytes((folder/src).read_bytes())
            shape=(32,32,32)
            data={'stdout.bin':b'Result = PASS','stderr.bin':b'',
                  'input-a.bin':struct.pack('<f',1.0)*1024,'input-b.bin':struct.pack('<f',0.01)*1024,
                  'output.bin':expected_output(shape),
                  'trace.json':json.dumps(dict(allocations=3,h2d=2,dtoh=1,launches=301,forwarded=301,frees=3,uploaded=2,metadata_injected=False)).encode()}
            for name,blob in data.items():(bundle/name).write_bytes(blob)
            row=dict(mode='trace',shape=list(shape),bundle='virtual-app-runs/capture',payloads=app_payloads(files,'trace'),command=argv_for(bundle,shape),policy_environment=TARGET,observations={n:digest(bundle/n) for n in data},exit_code=0)
            check_app(folder,files,row)
            for key,value in [('policy_environment',None),('command',['fake']),('exit_code',False),('mode','nominal'),('shape',[True,32,32]),('bundle','../outside')]:
                bad=copy.deepcopy(row);bad[key]=value
                with self.assertRaises(ValueError):check_app(folder,files,bad)
            (bundle/'output.bin').write_bytes(struct.pack('<I',0x7fc00000)*1024)
            with self.assertRaises(ValueError):check_app(folder,files,row)
            row['observations']['output.bin']=digest(bundle/'output.bin')
            with self.assertRaises(ValueError):check_app(folder,files,row)

if __name__=='__main__':unittest.main()
