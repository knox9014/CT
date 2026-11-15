import struct
import hashlib
import tempfile
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from matrix_kernel_check import CASES,geometry,dot_words,input_buffers,input_files,validate_case,preflight,entry_map,validate_job,validate_report,omission_matches,NAN
from run_matrix_kernels import verify_run

class MatrixKernelChecks(unittest.TestCase):
    def test_integer_dot_has_independent_nonsymmetric_expectations(self):
        actual=dot_words([1,2,3,4],[5,6,7,8],2,2,2)
        self.assertEqual(struct.pack('<4I',*actual),struct.pack('<4f',19/128,22/128,43/128,50/128))
    def test_closed_geometries_reject_partial_and_oversized_or_bool_shapes(self):
        self.assertEqual(geometry(CASES[-1]),((3,2,1),(32,32,1)))
        for case in ((16,17,16,16),(32,64,0,96),(64,64,64,64),(True,16,16,16),(16,16,16,16,1)):
            with self.assertRaises(ValueError):geometry(case)
    def test_noop_nan_and_input_or_guard_corruption_fail(self):
        case=CASES[0];inputs,expected=input_buffers(193,case)
        good=dict(a=inputs['a'],b=inputs['b'],c=expected)
        self.assertTrue(validate_case(193,case,inputs,good))
        self.assertFalse(validate_case(193,case,inputs,dict(a=inputs['a'],b=inputs['b'],c=inputs['c'])))
        for key,index in (('a',64),('b',-1),('c',0),('c',-1),('c',64+4*255)):
            bad=dict(good);data=bytearray(bad[key]);data[index]^=1;bad[key]=bytes(data)
            self.assertFalse(validate_case(193,case,inputs,bad))
    def test_each_seed_changes_both_input_matrices(self):
        first,_=input_buffers(193,CASES[-1]);second,_=input_buffers(194,CASES[-1])
        self.assertTrue(first['a']!=second['a'],'A must change with seed');self.assertTrue(first['b']!=second['b'],'B must change with seed')
    def test_full_profile_preflight_rejects_insufficient_device_or_fake_ptx(self):
        preflight([1024,1024,1024,1024,65535,65535,65535])
        for limits in ([512,1024,1024,1024,65535,65535,65535],[1024,16,1024,1024,65535,65535,65535],[1024,1024,1024,1024,1,65535,65535]):
            with self.assertRaises(ValueError):preflight(limits)
        with self.assertRaises(ValueError):entry_map(b'.entry _Z13MatrixMulCUDAILi16EEvPfS0_S0_ii(){}')
    def test_worker_completion_report_requires_all_cases_and_strict_types(self):
        value=dict(status='completed',seed=193,adapter='Intel test adapter',limits=[1024]*4+[65535]*3,
                   cases=[dict(case=list(case),grid=list(geometry(case)[0]),block=list(geometry(case)[1]),output_words=case[1]*case[3]) for case in CASES],cleanup='pass')
        self.assertTrue(validate_report(value,193))
        value['cases'][-1]['grid'][-1]=True;self.assertFalse(validate_report(value,193))
        value['cases'][-1]['grid'][-1]=1;value['cleanup']='failed';self.assertFalse(validate_report(value,193))
    def test_job_rejects_artifact_drift_resigned_inputs_and_stale_outputs(self):
        cache=Path(__file__).resolve().parents[1]/'.cache/matrix-job-tests';cache.mkdir(exist_ok=True,parents=True)
        with tempfile.TemporaryDirectory(dir=cache) as tmp:
            folder=Path(tmp);data=input_files(193);data.update({'nvcuda.dll':b'fake DLL never loaded','matrix.ptx':b'fake PTX never submitted'})
            for name,blob in data.items():(folder/name).write_bytes(blob)
            pins={n:hashlib.sha256(blob).hexdigest() for n,blob in data.items()};job=dict(schema_version=1,seed=193,files=pins)
            original=pins['case-0-a.bin'];pins['case-0-a.bin']='0'*64
            with self.assertRaisesRegex(ValueError,'artifact drift'):validate_job(job,folder)
            pins['case-0-a.bin']=original
            changed=bytearray(data['case-0-a.bin']);changed[64]^=1;(folder/'case-0-a.bin').write_bytes(changed);pins['case-0-a.bin']=hashlib.sha256(changed).hexdigest()
            with self.assertRaisesRegex(ValueError,'input recipe'):validate_job(job,folder)
            (folder/'case-0-a.bin').write_bytes(data['case-0-a.bin']);pins['case-0-a.bin']=original
            (folder/'case-0-c-readback.bin').write_bytes(b'stale')
            with self.assertRaisesRegex(ValueError,'stale'):validate_job(job,folder)
    def test_omission_controls_have_specific_completed_buffer_signatures(self):
        inputs,_=input_buffers(193,CASES[0])
        self.assertTrue(omission_matches('noop_launch',inputs,inputs))
        poisoned={k:struct.pack('<I',NAN)*(len(v)//4) for k,v in inputs.items()}
        self.assertTrue(omission_matches('noop_copy',inputs,poisoned))
        self.assertFalse(validate_case(193,CASES[0],inputs,poisoned))
        poisoned['c']=b'\0'*len(poisoned['c']);self.assertFalse(omission_matches('noop_copy',inputs,poisoned))

class MatrixObservationChecks(unittest.TestCase):
    """Synthetic observation protocol tests; these never execute GPU code."""
    def make_record(self,mode):
        root=Path(__file__).resolve().parents[1];cache=root/'.cache/matrix-observation-tests';cache.mkdir(exist_ok=True,parents=True)
        temporary=tempfile.TemporaryDirectory(dir=cache);self.addCleanup(temporary.cleanup);folder=Path(temporary.name)
        data={n:('synthetic '+n).encode() for n in ('ct_cuda.dll','host-noop.dll','copy-noop.dll','matrix.ptx','matrix.spv')}
        files={n:hashlib.sha256(blob).hexdigest() for n,blob in data.items()}
        bundle=folder/'matrix-kernel-runs/record';bundle.mkdir(parents=True)
        provider={'positive':'ct_cuda.dll','noop_launch':'host-noop.dll','noop_copy':'copy-noop.dll'}[mode]
        (bundle/'nvcuda.dll').write_bytes(data[provider]);(bundle/'matrix.ptx').write_bytes(data['matrix.ptx'])
        if mode!='positive':(bundle/'ct_underlying.dll').write_bytes(data['ct_cuda.dll'])
        for name,blob in input_files(193).items():(bundle/name).write_bytes(blob)
        pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.iterdir()}
        (bundle/'job.json').write_text(json.dumps(dict(schema_version=1,seed=193,files=pins)))
        pins=dict(pins,**{'job.json':hashlib.sha256((bundle/'job.json').read_bytes()).hexdigest()})
        report=dict(status='completed',seed=193,adapter='Intel synthetic observation',limits=[1024]*4+[65535]*3,
                    cases=[dict(case=list(c),grid=list(geometry(c)[0]),block=list(geometry(c)[1]),output_words=c[1]*c[3]) for c in CASES],cleanup='pass')
        (bundle/'stdout.json').write_text(json.dumps(report));(bundle/'stderr.txt').write_bytes(b'')
        for i,case in enumerate(CASES):
            inputs,expected=input_buffers(193,case)
            for key,blob in inputs.items():(bundle/f'case-{i}-{key}-readback.bin').write_bytes(expected if key=='c' and mode=='positive' else blob)
        names=[f'case-{i}-{k}-readback.bin' for i in range(len(CASES)) for k in ('a','b','c')]+['stdout.json','stderr.txt']
        row=dict(mode=mode,seed=193,bundle=bundle.relative_to(folder).as_posix(),command=[sys.executable,str(root/'scripts/matrix_kernel_worker.py'),str(bundle/'job.json')],files=pins,outputs={n:hashlib.sha256((bundle/n).read_bytes()).hexdigest() for n in names},exit_code=0,numerical=[mode=='positive']*len(CASES))
        return folder,files,row
    def test_successful_observations_reject_api_failure_or_relabelled_numerics(self):
        folder,files,row=self.make_record('positive');verify_run(folder,files,row)
        row['exit_code']=1
        with self.assertRaises(ValueError):verify_run(folder,files,row)
        row['exit_code']=0;row['numerical'][0]=False
        with self.assertRaises(ValueError):verify_run(folder,files,row)
    def test_control_requires_specific_signature_after_api_success(self):
        folder,files,row=self.make_record('noop_launch');verify_run(folder,files,row)
        row['numerical'][0]=True
        with self.assertRaises(ValueError):verify_run(folder,files,row)
        folder,files,row=self.make_record('noop_copy')
        with self.assertRaises(ValueError):verify_run(folder,files,row)

if __name__=='__main__':unittest.main()
