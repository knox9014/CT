"""R1b rounding-sensitive inputs of unchanged original matrix PTX, not new EXE inputs."""
import argparse
import json
from pathlib import Path
import sys
import uuid
import matrix_rounding_check as contract
from run_matrix_kernels import observe,verify_run
from run_matrix_breadth import build as build_parent,audit as audit_parent
from run_relaxed_nvcc import digest,verify_files
from run_validation import source_fingerprint

ROOT=Path(__file__).resolve().parents[1]
SCOPE='diagnostic_original_matrix_rounding_v1'
PROFILE=dict(job_schema=3,cases=[list(c) for c in contract.CASES],seeds=list(contract.SEEDS),
             recipes=['rounded_decimal','fused_residual'],ulp_tolerance=0,
             real_dot_bound='gamma(K)*sum(abs(a*b)); u=2^-24; gamma(K)=K/(2^24-K)',
             rounding_mode='sequential binary32 FMA RN-even',guard_words=16,
             output_words_per_positive=sum(c[1]*c[3] for c in contract.CASES))
SCENARIOS=tuple(('positive',s) for s in contract.SEEDS)+tuple((mode,s) for mode in ('noop_launch','noop_copy') for s in (193,194))
FIELDS={'schema_version','scope','release_claim','source_fingerprint','parent_sha256','files','case_profile','runs'}

def check_runs(folder,files,rows):
    if type(rows) is not list or any(type(r) is not dict for r in rows) or [(r.get('mode'),r.get('seed')) for r in rows]!=list(SCENARIOS):raise ValueError('rounding run set differs')
    reports=[verify_run(folder,files,r,contract=contract) for r in rows]
    if any((r['adapter'],r['limits'])!=(reports[0]['adapter'],reports[0]['limits']) for r in reports):raise ValueError('rounding device changed')

def audit(path):
    path=Path(path).resolve();folder=path.parent;m=json.loads(path.read_bytes())
    if (not folder.is_relative_to(ROOT/'.cache/runtime-attribute-runs') or set(m)!=FIELDS
            or type(m['schema_version']) is not int or m['schema_version']!=1
            or m['scope']!=SCOPE or m['release_claim'] is not False
            or not contract.exact(m['case_profile'],PROFILE)):raise ValueError('rounding manifest scope')
    if m['source_fingerprint']!=source_fingerprint(ROOT):raise ValueError('rounding source drift')
    parent=folder/'matrix-breadth-manifest.json'
    if digest(parent)!=m['parent_sha256']:raise ValueError('rounding parent drift')
    audit_parent(parent)
    expected=json.loads((folder/'matrix-kernel-manifest.json').read_bytes())['files']
    if not contract.exact(m['files'],expected):raise ValueError('rounding provider identities differ')
    verify_files(folder,m['files']);contract.entry_map((folder/'matrix.ptx').read_bytes())
    check_runs(folder,m['files'],m['runs']);return m

def build(validator):
    if sys.flags.optimize:raise ValueError('unoptimized rounding verification required')
    parent=build_parent(validator);folder=parent.parent;fp=source_fingerprint(ROOT)
    if json.loads(parent.read_bytes())['source_fingerprint']!=fp:raise ValueError('rounding parent source differs')
    files=json.loads((folder/'matrix-kernel-manifest.json').read_bytes())['files']
    rows=[observe(folder,files,mode,seed,contract=contract) for mode,seed in SCENARIOS]
    if source_fingerprint(ROOT)!=fp:raise ValueError('rounding source changed during execution')
    path=folder/'matrix-rounding-manifest.json'
    path.write_text(json.dumps(dict(schema_version=1,scope=SCOPE,release_claim=False,source_fingerprint=fp,
        parent_sha256=digest(parent),files=files,case_profile=PROFILE,runs=rows),indent=2)+'\n')
    audit(path)
    (ROOT/'.cache/matrix-rounding-latest.json').write_text(json.dumps(dict(manifest=path.relative_to(ROOT).as_posix()))+'\n')
    return path

def replay(path):
    m=audit(path);path=Path(path).resolve();folder=path.parent;sha=digest(path)
    rows=[observe(folder,m['files'],mode,seed,contract=contract) for mode,seed in SCENARIOS]
    check_runs(folder,m['files'],rows)
    if any(not contract.exact(old['outputs'],new['outputs']) for old,new in zip(m['runs'],rows)):raise ValueError('rounding deterministic replay differs')
    audit(path)
    if digest(path)!=sha or source_fingerprint(ROOT)!=m['source_fingerprint']:raise ValueError('rounding replay drift')
    report=folder/('matrix-rounding-replay-'+uuid.uuid4().hex+'.json')
    report.write_text(json.dumps(dict(manifest_sha256=sha,source_fingerprint=m['source_fingerprint'],release_claim=False,runs=rows),indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group();g.add_argument('--audit',type=Path);g.add_argument('--replay',type=Path)
    p.add_argument('--validator',type=Path,default=ROOT/'.cache/universal-foundation/spirv-build/tools/Release/spirv-val.exe');args=p.parse_args()
    if sys.flags.optimize:raise ValueError('unoptimized rounding verification required')
    if args.audit:path=args.audit;audit(path)
    elif args.replay:path=replay(args.replay)
    else:path=build(args.validator)
    print(json.dumps(dict(status='pass',scope=SCOPE,record=path.resolve().relative_to(ROOT).as_posix(),release_claim=False)))
