import json
import math
import struct
import unittest
import hashlib
import sys
import tempfile
import subprocess
from pathlib import Path

from upstream_vectoradd_oracle import validate_buffers, validate_trace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_upstream_vectoradd import check_run, check_set, STDOUT


class UpstreamVectorAddTests(unittest.TestCase):
    @staticmethod
    def buffers():
        a = [0.0, 0.125, 0.5, 1.0, 0.12345, 0.87654, 0.25, 0.99]
        b = [1.0, 0.875, 0.5, 0.0, 0.87654, 0.12345, 0.75, 0.01]
        pack = lambda v: struct.pack('<8f', *v)
        left, right = pack(a), pack(b)
        a, b = struct.unpack('<8f', left), struct.unpack('<8f', right)
        return left, right, pack([x + y for x,y in zip(a,b)])

    def test_exact_finite_sum(self):
        self.assertFalse(validate_buffers(*self.buffers(), count=8))

    def test_every_output_word_and_nan_inf_rejected(self):
        a,b,c = self.buffers()
        for index in range(8):
            for bad in (float('nan'), float('inf'), -1.0):
                value = bytearray(c);struct.pack_into('<f',value,index*4,bad)
                self.assertTrue(validate_buffers(a,b,bytes(value),count=8))

    def test_shape_and_input_finiteness(self):
        a,b,c = self.buffers()
        self.assertTrue(validate_buffers(a[:-1],b,c,count=8))
        self.assertTrue(validate_buffers(a,b,c+b'\0',count=8))
        self.assertTrue(validate_buffers(struct.pack('<8f',*([math.nan]*8)),b,c,count=8))

    def test_closed_trace_contract(self):
        trace = dict(device='Intel(R) Arc(TM) B390 GPU', allocations=3, h2d=2,
                     dtoh=1, launches=1, forwarded=1, frees=3, bytes=200000)
        self.assertFalse(validate_trace(trace))
        for key in trace:
            bad = dict(trace);bad[key] = 'wrong' if key == 'device' else True
            self.assertTrue(validate_trace(bad))
        bad = dict(trace);bad['extra'] = 0
        self.assertTrue(validate_trace(bad))
        trace['forwarded'] = 0
        self.assertFalse(validate_trace(trace, noop=True))
        self.assertTrue(validate_trace(trace))

    def test_noop_requires_valid_inputs_despite_expected_nan_output(self):
        cache=Path(__file__).resolve().parents[1]/'.cache/upstream-vectoradd-tests'
        cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as temporary:
            folder=Path(temporary);bundle=folder/'runs'/'noop';bundle.mkdir(parents=True)
            files={'vectorAdd.exe':'1'*64,'trace_noop.dll':'2'*64,'ct_cudart.dll':'3'*64,'ct_cuda.dll':'4'*64}
            payload={'vectorAdd.exe':b'exe','nvcuda.dll':b'noop','cudart64_12.dll':b'runtime','ct_underlying.dll':b'driver'}
            roles={'vectorAdd.exe':'vectorAdd.exe','nvcuda.dll':'trace_noop.dll','cudart64_12.dll':'ct_cudart.dll','ct_underlying.dll':'ct_cuda.dll'}
            for name,data in payload.items():
                (bundle/name).write_bytes(data);files[roles[name]]=hashlib.sha256(data).hexdigest()
            trace=dict(device='Intel(R) Arc(TM) B390 GPU',allocations=3,h2d=2,dtoh=1,launches=1,forwarded=0,frees=3,bytes=200000)
            data={'stdout.bin':STDOUT,'stderr.bin':b'','input-a.bin':struct.pack('<f',0.25)*50000,
                  'input-b.bin':struct.pack('<f',0.5)*50000,'output.bin':struct.pack('<I',0x7fc00000)*50000,
                  'trace.json':json.dumps(trace).encode()}
            for name,raw in data.items():(bundle/name).write_bytes(raw)
            row=dict(mode='noop',bundle='runs/noop',payloads={n:files[r] for n,r in roles.items()},
                     observations={n:hashlib.sha256(v).hexdigest() for n,v in data.items()},exit_code=0)
            check_run(folder,files,row)
            for raw in (b'',struct.pack('<f',math.nan)*50000):
                (bundle/'input-a.bin').write_bytes(raw);row['observations']['input-a.bin']=hashlib.sha256(raw).hexdigest()
                with self.assertRaises(ValueError):check_run(folder,files,row)

    def test_optimized_python_cannot_skip_independent_gpu_checks(self):
        code="import sys;sys.path.insert(0,'scripts');from pathlib import Path;import run_upstream_vectoradd as r\ntry:r.independent_driver(Path('.cache/missing-optimized-input'))\nexcept ValueError as e:print(str(e))"
        run=subprocess.run([sys.executable,'-O','-c',code],cwd=Path(__file__).resolve().parents[1],capture_output=True,timeout=30)
        self.assertEqual(run.returncode,0)
        self.assertEqual(run.stdout.strip(),b'independent Driver checks require unoptimized Python')

    def test_valid_but_different_control_inputs_are_rejected(self):
        cache=Path(__file__).resolve().parents[1]/'.cache/upstream-vectoradd-tests';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as temporary:
            folder=Path(temporary);files={};rows=[]
            for mode in ('nominal','trace','noop'):
                bundle=folder/'runs'/mode;bundle.mkdir(parents=True)
                roles={'vectorAdd.exe':'vectorAdd.exe','cudart64_12.dll':'ct_cudart.dll',
                       'nvcuda.dll':{'nominal':'ct_cuda.dll','trace':'trace.dll','noop':'trace_noop.dll'}[mode]}
                if mode!='nominal':roles['ct_underlying.dll']='ct_cuda.dll'
                for name,role in roles.items():
                    data=role.encode();(bundle/name).write_bytes(data);files[role]=hashlib.sha256(data).hexdigest()
                data={'stdout.bin':STDOUT,'stderr.bin':b''}
                if mode!='nominal':
                    data.update({'input-a.bin':struct.pack('<f',0.25)*50000,'input-b.bin':struct.pack('<f',0.5)*50000,
                                 'output.bin':(struct.pack('<I',0x7fc00000) if mode=='noop' else struct.pack('<f',0.75))*50000,
                                 'trace.json':json.dumps(dict(device='Intel(R) Arc(TM) B390 GPU',allocations=3,h2d=2,dtoh=1,launches=1,forwarded=int(mode=='trace'),frees=3,bytes=200000)).encode()})
                for name,raw in data.items():(bundle/name).write_bytes(raw)
                rows.append(dict(mode=mode,bundle='runs/'+mode,payloads={n:files[r] for n,r in roles.items()},
                                 observations={n:hashlib.sha256(raw).hexdigest() for n,raw in data.items()},exit_code=0))
            check_set(folder,files,rows)
            changed=struct.pack('<f',0.75)*50000
            (folder/'runs/noop/input-a.bin').write_bytes(changed)
            rows[2]['observations']['input-a.bin']=hashlib.sha256(changed).hexdigest()
            check_run(folder,files,rows[2])
            with self.assertRaises(ValueError):check_set(folder,files,rows)


if __name__ == '__main__':
    unittest.main()
