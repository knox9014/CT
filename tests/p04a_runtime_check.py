"""Independent bounded scalar-global numerical oracle, without host expected values."""
import argparse, json, subprocess
from pathlib import Path
MASK=(1<<32)-1
N=17
GUARD=64
TOTAL=N+GUARD*2
CALLS=100

def expected(seed):
    inputs=[((seed*5+i*7)^0x2468ace0)&MASK for i in range(TOTAL)]
    initial=[((seed*3+i*11)^0x13579bdf)&MASK for i in range(TOTAL)]
    runs=[]
    for j in range(CALLS):
        output=initial.copy()
        output[GUARD:GUARD+N]=[(v+7+4*j+seed%13)&MASK for v in inputs[GUARD:GUARD+N]]
        runs.append(output)
    return dict(seed=seed, runs=runs, inputs=inputs, errors=[0]*(CALLS*2), main_entered=1)

def validate(value,seed):
    # Equality alone accepts bool==int in Python; require an exact closed integer schema.
    def integers(x):
        if isinstance(x,list): return all(integers(v) for v in x)
        return type(x) is int and 0<=x<=MASK
    if not isinstance(value,dict) or set(value)!=set(expected(seed)):return ['global oracle schema']
    if any(not integers(v) for v in value.values()):return ['global oracle value types']
    return [] if value==expected(seed) else ['global numerical/guard/input/sequence mismatch']

def execute(executable,seed):
    run=subprocess.run([str(executable.resolve()),str(seed)],cwd=executable.parent,capture_output=True,timeout=120)
    if run.returncode:raise ValueError('global host failed')
    value=json.loads(run.stdout)
    if validate(value,seed):raise ValueError('global oracle mismatch')
    return value

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exe',type=Path,required=True);p.add_argument('--seed',type=int,required=True);a=p.parse_args()
    try:
        execute(a.exe,a.seed)
        print(json.dumps(dict(status='pass',scope='diagnostic_runtime_globals',calls=CALLS,outputs=N,guards=GUARD*2)))
    except (OSError,ValueError,subprocess.SubprocessError):
        print(json.dumps(dict(status='fail',reason='runtime_global_oracle_failed')));raise SystemExit(1)
