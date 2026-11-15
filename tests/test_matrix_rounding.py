import hashlib,json,struct,sys,tempfile,unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import matrix_rounding_check as rounding
from fma_check import split_bits

class MatrixRoundingTests(unittest.TestCase):
    def test_reference_refuses_subnormal_intermediate_outside_closed_bound(self):
        rounding._reference.cache_clear()
        self.addCleanup(rounding._reference.cache_clear)
        with patch.object(rounding,'fused_bits',return_value=1):
            with self.assertRaises(ValueError):rounding.reference(193,rounding.CASES[0])

    def test_real_dot_budget_rejects_large_finite_error_and_nonfinite_values(self):
        case=rounding.CASES[1];count=case[1]*case[3]
        self.assertFalse(rounding.real_dot_bounds_valid(194,case,[0x3f800000]*count))
        self.assertFalse(rounding.real_dot_bounds_valid(193,case,[0x7f800000]*count))
        self.assertFalse(rounding.real_dot_bounds_valid(193,case,[True]*count))

    def test_observation_binds_rounding_command_and_schema3(self):
        from run_matrix_kernels import verify_run
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            folder=Path(name);bundle=folder/'matrix-kernel-runs/record';bundle.mkdir(parents=True)
            files={n:hashlib.sha256(n.encode()).hexdigest() for n in ('ct_cuda.dll','matrix.ptx')}
            for name in files:(bundle/('nvcuda.dll' if name=='ct_cuda.dll' else name)).write_bytes(name.encode())
            for name,data in rounding.input_files(193).items():(bundle/name).write_bytes(data)
            sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            pins={p.name:sha(p) for p in bundle.iterdir()}
            job=dict(schema_version=3,seed=193,files=pins);(bundle/'job.json').write_text(json.dumps(job))
            pins=dict(pins,**{'job.json':sha(bundle/'job.json')})
            report=dict(status='completed',seed=193,adapter='Intel synthetic observation',limits=[1024]*4+[65535]*3,cases=[dict(case=list(c),grid=list(rounding.geometry(c)[0]),block=list(rounding.geometry(c)[1]),output_words=c[1]*c[3]) for c in rounding.CASES],cleanup='pass')
            (bundle/'stdout.json').write_text(json.dumps(report));(bundle/'stderr.txt').write_bytes(b'')
            for i,case in enumerate(rounding.CASES):
                inputs,expected=rounding.input_buffers(193,case)
                for key,data in dict(inputs,c=expected).items():(bundle/f'case-{i}-{key}-readback.bin').write_bytes(data)
            outputs={p.name:sha(p) for p in bundle.iterdir() if p.name not in pins}
            cmd=[sys.executable,str(ROOT/'scripts/matrix_kernel_worker.py'),'--rounding-v1',str(bundle/'job.json')]
            row=dict(mode='positive',seed=193,bundle='matrix-kernel-runs/record',command=cmd,files=pins,outputs=outputs,exit_code=0,numerical=[True]*2)
            verify_run(folder,files,row,contract=rounding)
            row['command']=cmd[:2]+['--breadth-v1']+cmd[3:]
            with self.assertRaises(ValueError):verify_run(folder,files,row,contract=rounding)
            row['command']=cmd;job['schema_version']=2;(bundle/'job.json').write_text(json.dumps(job));row['files']['job.json']=sha(bundle/'job.json')
            with self.assertRaises(ValueError):verify_run(folder,files,row,contract=rounding)

    def test_capture_scope_budget_and_run_set_cannot_be_relaxed(self):
        import run_matrix_rounding as runner
        rows=[dict(mode=mode,seed=seed) for mode,seed in runner.SCENARIOS]
        with patch.object(runner,'verify_run',return_value=dict(adapter='synthetic',limits=[1024]*7)):
            runner.check_runs(Path('.'),{},rows)
            for bad in [rows[:-1],list(reversed(rows)),[dict(row,mode='positive') for row in rows]]:
                with self.assertRaises(ValueError):runner.check_runs(Path('.'),{},bad)
        cache=ROOT/'.cache/runtime-attribute-runs';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as name:
            profile=json.loads(json.dumps(runner.PROFILE));profile['ulp_tolerance']=1
            m=dict(schema_version=1,scope=runner.SCOPE,release_claim=False,source_fingerprint='a'*64,parent_sha256='b'*64,files={},case_profile=profile,runs=[])
            p=Path(name)/'matrix-rounding-manifest.json';p.write_text(json.dumps(m))
            with patch.object(runner,'source_fingerprint') as source,patch.object(runner,'audit_parent') as parent:
                with self.assertRaises(ValueError):runner.audit(p)
                source.assert_not_called();parent.assert_not_called()

    def test_cached_rounder_keeps_strict_scalar_types(self):
        rounding.round_fraction(Fraction(1));rounding.word_fraction(1)
        for value in (True,1.0):
            with self.assertRaises(ValueError):rounding.round_fraction(value)
            with self.assertRaises(ValueError):rounding.word_fraction(value)

    def test_worker_dispatch_is_closed_and_conflicting_profiles_fail_before_device(self):
        from run_matrix_kernels import worker_flags
        import matrix_kernel_check as base
        import matrix_breadth_check as breadth
        import matrix_kernel_worker as worker
        self.assertEqual(worker_flags(base),[])
        self.assertEqual(worker_flags(breadth),['--breadth-v1'])
        self.assertEqual(worker_flags(rounding),['--rounding-v1'])
        with self.assertRaises(ValueError):worker_flags(object())
        with patch.object(worker,'Device') as device:
            with self.assertRaises(ValueError):worker.execute('unused',breadth=True,rounding=True)
            device.assert_not_called()

    def test_independent_rounding_literal_anchors_and_ties(self):
        for value,want in [(Fraction(1,10),0x3dcccccd),(-Fraction(1,10),0xbdcccccd),(Fraction(1)+Fraction(1,2**24),0x3f800000),(Fraction(1)+Fraction(3,2**24),0x3f800002),(-Fraction(1)-Fraction(3,2**24),0xbf800002),(-Fraction(1,2**46),0xa8800000),(Fraction(),0)]:
            self.assertEqual(rounding.round_fraction(value),want)
        with self.assertRaises(ValueError):rounding.round_fraction(Fraction(1000))
        with self.assertRaises(ValueError):rounding.word_fraction(0x7f800000)

    def test_selected_sequential_dots_match_independent_fraction_rounding(self):
        for seed in rounding.SEEDS:
            for case in rounding.CASES:
                _,m,k,n=case;a,b=rounding.input_words(seed,case);words=rounding.reference(seed,case)
                for row,col in [(0,0),(m-1,n-1),(m//2,n//2)]:
                    total=0
                    for j in range(k):
                        term=rounding.word_fraction(a[row*k+j])*rounding.word_fraction(b[j*n+col])
                        total=rounding.round_fraction(term+rounding.word_fraction(total))
                    self.assertEqual(words[row*n+col],total)
                self.assertTrue(rounding.real_dot_bounds_valid(seed,case,words))

    def test_residual_discriminates_split_even_when_real_dot_bound_allows_zero(self):
        for seed in (193,295):
            for case in rounding.CASES:
                _,_,k,n=case;a,b=rounding.input_words(seed,case);split=0
                for j in range(k):split=split_bits(a[j],b[j*n],split)
                self.assertEqual(split,0)
                self.assertNotEqual(rounding.reference(seed,case)[0],split)
                inputs,expected=rounding.input_buffers(seed,case)
                zeros=rounding.packet([0]*(case[1]*case[3]))
                self.assertTrue(rounding.real_dot_bounds_valid(seed,case,[0]*(case[1]*case[3])))
                self.assertFalse(rounding.validate_case(seed,case,inputs,dict(inputs,c=zeros)))
                self.assertTrue(rounding.validate_case(seed,case,inputs,dict(inputs,c=expected)))

    def test_inputs_are_closed_and_distinct_and_invalid_outputs_fail(self):
        pairs=set()
        for seed in rounding.SEEDS:
            for case in rounding.CASES:
                inputs,expected=rounding.input_buffers(seed,case);pairs.add((case,inputs['a'],inputs['b']))
                good=dict(inputs,c=expected)
                self.assertTrue(rounding.validate_case(seed,case,inputs,good))
                self.assertFalse(rounding.validate_case(seed,case,inputs,inputs))
                for word in (0x7fc00000,0x7f800000):
                    bad=bytearray(expected);bad[64:68]=struct.pack('<I',word)
                    self.assertFalse(rounding.validate_case(seed,case,inputs,dict(good,c=bytes(bad))))
                for key,offset in [('a',64),('b',0),('c',64),('c',len(expected)-1)]:
                    bad=bytearray(good[key]);bad[offset]^=1
                    self.assertFalse(rounding.validate_case(seed,case,inputs,dict(good,**{key:bytes(bad)})))
        self.assertEqual(len(pairs),8)
        with self.assertRaises(ValueError):rounding.input_words(999,rounding.CASES[0])
        with self.assertRaises(ValueError):rounding.geometry((32,33,64,32))

if __name__=='__main__':unittest.main()
