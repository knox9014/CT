import hashlib,json,struct,sys,tempfile,unittest
from unittest.mock import patch
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import matrix_breadth_check as breadth

class BreadthTests(unittest.TestCase):
    def test_run_set_cannot_drop_reorder_or_relabel_a_case(self):
        import run_matrix_breadth as runner
        rows=[dict(mode=mode,seed=seed) for mode,seed in runner.SCENARIOS]
        with patch.object(runner,'verify_run',return_value=dict(adapter='synthetic',limits=[1024]*7)):
            runner.check_runs(Path('.'),{},rows)
            for bad in [rows[:-1],list(reversed(rows)),[dict(r,mode='positive') for r in rows]]:
                with self.assertRaises(ValueError):runner.check_runs(Path('.'),{},bad)

    def test_audit_refuses_new_source_before_trusting_parent(self):
        import run_matrix_breadth as runner
        cache=ROOT/'.cache/runtime-attribute-runs';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as name:
            path=Path(name)/'matrix-breadth-manifest.json'
            m=dict(schema_version=1,scope=runner.SCOPE,release_claim=False,source_fingerprint='a'*64,parent_sha256='b'*64,files={},case_profile=runner.PROFILE,runs=[])
            path.write_text(json.dumps(m))
            with patch.object(runner,'source_fingerprint',return_value='c'*64),patch.object(runner,'audit_parent') as parent:
                with self.assertRaises(ValueError):runner.audit(path)
                parent.assert_not_called()

    def test_audit_rejects_parent_provider_identity_and_actual_byte_drift(self):
        import run_matrix_breadth as runner
        cache=ROOT/'.cache/runtime-attribute-runs';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as name:
            folder=Path(name);parent=folder/'virtual-target-manifest.json';parent.write_bytes(b'synthetic parent')
            files={'ct_cuda.dll':hashlib.sha256(b'A').hexdigest()}
            (folder/'matrix-kernel-manifest.json').write_text(json.dumps(dict(files=files)))
            base=dict(schema_version=1,scope=runner.SCOPE,release_claim=False,source_fingerprint='a'*64,parent_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),files=files,case_profile=runner.PROFILE,runs=[])
            for mutation in ('parent','provider','bytes'):
                m=json.loads(json.dumps(base));(folder/'ct_cuda.dll').write_bytes(b'B' if mutation=='bytes' else b'A')
                if mutation=='parent':m['parent_sha256']='c'*64
                if mutation=='provider':m['files']['ct_cuda.dll']='c'*64
                path=folder/'matrix-breadth-manifest.json';path.write_text(json.dumps(m))
                with patch.object(runner,'source_fingerprint',return_value='a'*64),patch.object(runner,'audit_parent') as audit_parent,patch.object(runner,'check_runs') as runs:
                    with self.assertRaises(ValueError):runner.audit(path)
                    runs.assert_not_called()
                    if mutation=='parent':audit_parent.assert_not_called()

    def test_observation_binds_breadth_schema_command_and_all_seven_cases(self):
        from run_matrix_kernels import verify_run
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            folder=Path(name);bundle=folder/'matrix-kernel-runs/record';bundle.mkdir(parents=True)
            files={n:hashlib.sha256(n.encode()).hexdigest() for n in ('ct_cuda.dll','matrix.ptx')}
            for name in files:(bundle/('nvcuda.dll' if name=='ct_cuda.dll' else name)).write_bytes(name.encode())
            for name,data in breadth.input_files(193).items():(bundle/name).write_bytes(data)
            sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            pins={p.name:sha(p) for p in bundle.iterdir()}
            (bundle/'job.json').write_text(json.dumps(dict(schema_version=2,seed=193,files=pins)))
            pins=dict(pins,**{'job.json':sha(bundle/'job.json')})
            report=dict(status='completed',seed=193,adapter='Intel synthetic observation',limits=[1024]*4+[65535]*3,cases=[dict(case=list(c),grid=list(breadth.geometry(c)[0]),block=list(breadth.geometry(c)[1]),output_words=c[1]*c[3]) for c in breadth.CASES],cleanup='pass')
            (bundle/'stdout.json').write_text(json.dumps(report));(bundle/'stderr.txt').write_bytes(b'')
            for i,case in enumerate(breadth.CASES):
                inputs,expected=breadth.input_buffers(193,case)
                for key,data in dict(inputs,c=expected).items():(bundle/f'case-{i}-{key}-readback.bin').write_bytes(data)
            outputs={p.name:sha(p) for p in bundle.iterdir() if p.name not in pins}
            command=[sys.executable,str(ROOT/'scripts/matrix_kernel_worker.py'),'--breadth-v1',str(bundle/'job.json')]
            row=dict(mode='positive',seed=193,bundle='matrix-kernel-runs/record',command=command,files=pins,outputs=outputs,exit_code=0,numerical=[True]*7)
            verify_run(folder,files,row,contract=breadth)
            row['command']=command[:2]+command[3:]
            with self.assertRaises(ValueError):verify_run(folder,files,row,contract=breadth)
            row['command']=command;row['numerical']=[True]*4
            with self.assertRaises(ValueError):verify_run(folder,files,row,contract=breadth)

    def test_closed_geometry_and_resource_preflight(self):
        self.assertEqual(len(breadth.CASES),7)
        self.assertIn((32,64,128,32),breadth.CASES)
        for case in [(32,33,96,64),(32,64,129,32),(True,32,32,32)]:
            with self.assertRaises(ValueError):breadth.geometry(case)
        breadth.preflight([1024,1024,1024,64,65535,65535,65535])
        with self.assertRaises(ValueError):breadth.preflight([512,1024,1024,64,65535,65535,65535])

    def test_six_recipes_are_distinct_and_exact_fraction_oracle_matches(self):
        identities=set()
        for seed in breadth.SEEDS:
            all_inputs=breadth.input_files(seed)
            identities.add(hashlib.sha256(b''.join(all_inputs.values())).hexdigest())
            for case in breadth.CASES:
                _,m,k,n=case;a,b=breadth.coefficients(seed,case)
                words=breadth.dot_words(a,b,m,k,n)
                for row,col in [(0,0),(m-1,n-1),(m//2,n//2)]:
                    oracle=sum((Fraction(a[row*k+j],8)*Fraction(b[j*n+col],16) for j in range(k)),Fraction())
                    got=struct.unpack('<f',struct.pack('<I',words[row*n+col]))[0]
                    self.assertEqual(Fraction(got),oracle)
                if seed%3==2:self.assertEqual(set(words),{0})
        self.assertEqual(len(identities),6)

    def test_exact_readbacks_reject_nan_input_guard_and_single_word_corruption(self):
        for seed in (193,194,195):
            case=breadth.CASES[-1];inputs,expected=breadth.input_buffers(seed,case)
            good=dict(inputs,c=expected)
            self.assertTrue(breadth.validate_case(seed,case,inputs,good))
            self.assertFalse(breadth.validate_case(seed,case,inputs,inputs))
            for key,offset in [('a',0),('b',breadth.GUARDS*4),('c',breadth.GUARDS*4),('c',len(expected)-1)]:
                bad=dict(good);data=bytearray(bad[key]);data[offset]^=1;bad[key]=bytes(data)
                self.assertFalse(breadth.validate_case(seed,case,inputs,bad))

    def test_new_job_schema_does_not_accept_baseline_or_missing_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            for schema in (1,2,True):
                with self.assertRaises(ValueError):breadth.validate_job(dict(schema_version=schema,seed=193,files={}),Path(name))

if __name__=='__main__':unittest.main()
