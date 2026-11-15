"""Independent symbol/copy/module-state oracle; executable prints observations only."""
MASK=(1<<32)-1
N=17
GUARD=64
TOTAL=N+GUARD*2
CALLS=100
def expected(seed,order):
    contexts=[]
    for ctx in range(2):
        inputs=[((seed*5+ctx*23+i*7)^0x2468ace0)&MASK for i in range(TOTAL)]
        initial=[((seed*3+ctx*31+i*11)^0x13579bdf)&MASK for i in range(TOTAL)]
        bias=seed%13+ctx
        def output(a,b):
            result=initial.copy()
            result[GUARD:GUARD+N]=[(v+a+b+bias)&MASK for v in inputs[GUARD:GUARD+N]]
            return result
        runs=[];before=[];after=[];partial_reads=[]
        for j in range(CALLS):
            raw=((seed*17+ctx*101+j*13)^0xa5c35a7e)&MASK
            patch=(seed+ctx*31+j*19)&0xffff
            v=(raw&0xff0000ff)|(patch<<8)
            partial_reads.append([0xa6]*GUARD+[(v>>8)&255,(v>>16)&255]+[0xa6]*GUARD)
            before.append([v,v]);runs.append(output(v,v));after.append([(v+1)&MASK,(v+3)&MASK])
        contexts.append(dict(bootstrap=output(7,29),runs=runs,inputs=inputs,before=before,after=after,partial_reads=partial_reads,final=after[-1]))
    return dict(seed=seed,order=order,contexts=contexts,negative=[1]*8,revisit=contexts[0]['final'],main_entered=1)
def expected_noop(seed,order):
    value=expected(seed,order)
    for ctx,context in enumerate(value['contexts']):
        initial=[((seed*3+ctx*31+i*11)^0x13579bdf)&MASK for i in range(TOTAL)]
        context['bootstrap']=initial.copy()
        context['runs']=[initial.copy() for _ in range(CALLS)]
        context['after']=[row.copy() for row in context['before']]
        context['final']=context['after'][-1].copy()
    value['revisit']=value['contexts'][0]['final'].copy()
    return value
def _validate(value,wanted):
    def shape(actual,wanted):
        if isinstance(wanted,dict):
            return isinstance(actual,dict) and set(actual)==set(wanted) and all(shape(actual[k],v) for k,v in wanted.items())
        if isinstance(wanted,list):return isinstance(actual,list) and len(actual)==len(wanted) and all(shape(a,b) for a,b in zip(actual,wanted))
        return type(actual) is int and 0<=actual<=MASK
    if not shape(value,wanted):return ['symbol oracle closed schema/types']
    return [] if value==wanted else ['symbol numerical/guard/input/state/context mismatch']
def validate(value,seed,order):return _validate(value,expected(seed,order))
def validate_noop(value,seed,order):return _validate(value,expected_noop(seed,order))
