"""Independent expectations must reject no-op, guard and state corruption."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from p04b_symbol_check import expected,validate,expected_noop,validate_noop
class SymbolOracleTests(unittest.TestCase):
    def test_partial_read_bytes_and_host_guards(self):
        for seed in (1,773,999999):
            for order in (0,1):
                value=expected(seed,order)
                for ctx,context in enumerate(value['contexts']):
                    for j,row in enumerate(context['partial_reads']):
                        patch=(seed+ctx*31+j*19)&0xffff
                        self.assertEqual(row,[0xa6]*64+[patch&255,patch>>8]+[0xa6]*64)
                for index in (0,63,64,65,66,129):
                    bad=copy.deepcopy(value)
                    bad['contexts'][1]['partial_reads'][99][index]^=1
                    self.assertTrue(validate(bad,seed,order))
                noop=expected_noop(seed,order)
                self.assertEqual(validate_noop(noop,seed,order),[])
                bad=copy.deepcopy(noop)
                bad['contexts'][0]['partial_reads'][0][64]^=1
                self.assertTrue(validate_noop(bad,seed,order))

    def test_symbol_oracle_closed_and_sensitive(self):
        for seed in (1,773,999999):
            for order in (0,1):
                value=expected(seed,order)
                self.assertEqual(validate(value,seed,order),[])
                for target in ('guard','input','symbol','revisit','context','error','bool','extra','seed','order'):
                    bad=copy.deepcopy(value)
                    if target=='guard':bad['contexts'][0]['runs'][0][0]^=1
                    if target=='input':bad['contexts'][0]['inputs'][0]^=1
                    if target=='symbol':bad['contexts'][1]['after'][0][0]^=1
                    if target=='revisit':bad['revisit'][0]^=1
                    if target=='context':bad['contexts'][1]=bad['contexts'][0]
                    if target=='error':bad['negative'][0]=0
                    if target=='bool':bad['main_entered']=True
                    if target=='extra':bad['extra']=0
                    if target=='seed':bad['seed']+=1
                    if target=='order':bad['order']=1-order
                    with self.subTest(seed=seed,order=order,target=target):self.assertTrue(validate(bad,seed,order))
    def test_noop_outputs_fail(self):
        value=expected(123,0)
        for context in value['contexts']:
            context['runs']=[context['inputs'] for _ in context['runs']]
        self.assertTrue(validate(value,123,0))
    def test_noop_control_requires_exact_preserved_inputs_and_guards(self):
        value=expected_noop(123,0)
        self.assertEqual(validate_noop(value,123,0),[])
        self.assertTrue(validate(value,123,0))
        self.assertTrue(validate_noop({},123,0))
        self.assertTrue(validate_noop(expected(123,0),123,0))
        for key in ('guard','input','error','symbol'):
            bad=copy.deepcopy(value)
            if key=='guard':bad['contexts'][0]['runs'][0][0]^=1
            if key=='input':bad['contexts'][1]['inputs'][64]^=1
            if key=='error':bad['negative'][0]=0
            if key=='symbol':bad['contexts'][0]['after'][0][0]^=1
            self.assertTrue(validate_noop(bad,123,0))
