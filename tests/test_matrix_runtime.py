import copy
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from matrix_runtime_check import buffers_valid, trace_valid, scope_valid, expected_output
from run_matrix_runtime import check_run,argv_for,payloads
from run_relaxed_nvcc import digest

class MatrixRuntimeTests(unittest.TestCase):
    def test_all_words_finite_and_correct(self):
        shape=(32,32,32);m,k,n=shape
        a=struct.pack('<f',1.0)*(m*k);b=struct.pack('<f',0.01)*(k*n)
        c=expected_output(shape)
        self.assertTrue(buffers_valid(shape,a,b,c))
        for word in (0x7fc00000,0x7f800000,0,0x3f800000):
            self.assertFalse(buffers_valid(shape,a,b,c[:-4]+struct.pack('<I',word)))
        for bad in (c[:-1],c+b'\0'):
            self.assertFalse(buffers_valid(shape,a,b,bad))
        self.assertFalse(buffers_valid(shape,a[:-4]+b'\0'*4,b,c))
        self.assertFalse(buffers_valid(shape,a,b[:-4]+b'\0'*4,c))

    def test_closed_trace_and_omission_modes(self):
        value=dict(allocations=3,h2d=2,dtoh=1,launches=301,forwarded=301,frees=3,
                   uploaded=2,metadata_injected=True)
        self.assertTrue(trace_valid(value,'positive'))
        for key in value:
            bad=copy.deepcopy(value);bad[key]=False
            self.assertFalse(trace_valid(bad,'positive'))
        self.assertFalse(trace_valid(dict(value,extra=1),'positive'))
        self.assertTrue(trace_valid(dict(value,forwarded=0),'noop_launch'))
        self.assertTrue(trace_valid(dict(value,uploaded=0),'noop_copy'))
        self.assertFalse(trace_valid(value,'unknown'))

    def test_scope_never_production_compatible(self):
        value=dict(metadata_injected=True,production_compatible=False,release_claim=False,
                   injected_compute_capability=[5,2])
        self.assertTrue(scope_valid(value))
        for key in ('metadata_injected','production_compatible','release_claim'):
            bad=copy.deepcopy(value);bad[key]=not value[key]
            self.assertFalse(scope_valid(bad))
        self.assertFalse(scope_valid(dict(value,injected_compute_capability=[True,2])))

    def test_observation_audit_rejects_relabelled_commands_and_raw_mutations(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.cache') as tmp:
            folder=Path(tmp).resolve();bundle=folder/'matrix-runtime-runs'/'capture';bundle.mkdir(parents=True)
            shape=(32,32,32);files={n:'0'*64 for n in ('ct_cuda.dll','matrix-runtime-original.dll','matrixMul.exe','metadata.dll','positive.dll')}
            for name in files:
                (folder/name).write_bytes(name.encode());files[name]=digest(folder/name)
            pins=payloads(files,'positive')
            source={'matrixMul.exe':'matrixMul.exe','ct_underlying.dll':'ct_cuda.dll','nvcuda.dll':'positive.dll','cudart64_12.dll':'metadata.dll','ct_runtime.dll':'matrix-runtime-original.dll'}
            for dst,src in source.items():(bundle/dst).write_bytes((folder/src).read_bytes())
            data={'stdout.bin':b'Result = PASS','stderr.bin':b'',
                  'metadata.json':json.dumps(dict(major_queries=1,minor_queries=1,major=5,minor=2)).encode(),
                  'trace.json':json.dumps(dict(allocations=3,h2d=2,dtoh=1,launches=301,forwarded=301,frees=3,uploaded=2,metadata_injected=True)).encode(),
                  'input-a.bin':struct.pack('<f',1.0)*1024,'input-b.bin':struct.pack('<f',0.01)*1024,'output.bin':expected_output(shape)}
            for name,blob in data.items():(bundle/name).write_bytes(blob)
            row=dict(mode='positive',shape=list(shape),bundle='matrix-runtime-runs/capture',command=argv_for(bundle,shape),payloads=pins,observations={n:digest(bundle/n) for n in data},exit_code=0,numerically_valid=True)
            check_run(folder,files,row)
            for field,replacement in [('exit_code',False),('numerically_valid',1),('shape',[True,32,32]),('bundle','../outside'),('command',['fake']),('payloads',{})]:
                bad=copy.deepcopy(row);bad[field]=replacement
                with self.assertRaises(ValueError):check_run(folder,files,bad)
            (bundle/'output.bin').write_bytes(struct.pack('<I',0x7fc00000)*1024)
            with self.assertRaises(ValueError):check_run(folder,files,row)
            row['observations']['output.bin']=digest(bundle/'output.bin')
            with self.assertRaises(ValueError):check_run(folder,files,row)

if __name__=='__main__':unittest.main()
