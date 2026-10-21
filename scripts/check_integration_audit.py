"""Check a PR dependency snapshot and independently identified local candidate."""
import argparse
import json
from pathlib import Path
import subprocess
from compatibility_registry import digest, fields, ident, member, strings, LANES


def validate_stack(data: dict) -> list[str]:
    if (not fields(data, 'schema_version source_baseline base_commit pull_requests')
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or not digest(data['source_baseline'],40) or not digest(data['base_commit'],40)
            or not isinstance(data['pull_requests'],list)):
        return ['invalid stack fields']
    errors, nodes = [], {}
    for node in data['pull_requests']:
        if (not fields(node,'id base head depends_on review_baseline') or type(node['id']) is not int
                or node['id'] <= 0 or node['id'] in nodes or not digest(node['head'],40)
                or not digest(node['review_baseline'],40)
                or (node['base'] is not None and type(node['base']) is not int)
                or not isinstance(node['depends_on'],list)
                or any(type(n) is not int for n in node['depends_on'])
                or len(node['depends_on']) != len(set(node['depends_on']))):
            errors.append('invalid or duplicate stack node'); continue
        nodes[node['id']]=node
    for node in nodes.values():
        if any(n not in nodes for n in node['depends_on']): errors.append('unknown dependency')
        if node['base'] is not None and node['base'] not in node['depends_on']:
            errors.append('unknown or undeclared base')
    remaining=set(nodes)
    while remaining:
        ready={n for n in remaining if not set(nodes[n]['depends_on']) & remaining}
        if not ready:
            errors.append('stack cycle');break
        remaining-=ready
    return errors


def validate_integration_report(report: dict, stack: dict, *, expected_candidate=None,
                                expected_tree=None, expected_clean=None, expected_cases=None) -> list[str]:
    errors=validate_stack(stack)
    if errors:return errors
    if (not fields(report,'schema_version candidate_commit source_tree_sha256 clean release_claim remote_snapshot_status remote_heads required_lanes lane_reports')
            or type(report['schema_version']) is not int or report['schema_version'] != 1
            or not digest(report['candidate_commit'],40) or not digest(report['source_tree_sha256'])
            or type(report['clean']) is not bool or type(report['release_claim']) is not bool
            or not member(report['remote_snapshot_status'],('observed','not_run'))
            or not isinstance(report['remote_heads'],dict)
            or not strings(report['required_lanes'],lambda x: member(x,LANES))
            or not isinstance(report['lane_reports'],list)):
        return errors+['invalid integration report fields']
    if expected_candidate is not None and report['candidate_commit'] != expected_candidate:
        errors.append('candidate differs from observed source')
    if expected_tree is not None and report['source_tree_sha256'] != expected_tree:
        errors.append('tree differs from observed source')
    if expected_clean is not None and report['clean'] != expected_clean:
        errors.append('clean state differs from observed source')
    if report['release_claim']:
        errors.append('foundation validation does not authorize release claims')
    if report['release_claim'] and (not report['clean'] or expected_candidate is None
            or expected_tree is None or report['remote_snapshot_status'] != 'observed'):
        errors.append('release requires clean, independently identified candidate and remote observation')
    heads = {str(n['id']):n['head'] for n in stack.get('pull_requests',[]) if isinstance(n,dict) and 'id' in n and 'head' in n}
    if report['remote_snapshot_status']=='observed' and report['remote_heads'] != heads:
        errors.append('stale or incomplete remote snapshot')
    if report['remote_snapshot_status']=='not_run' and report['remote_heads']:
        errors.append('unobserved remote cannot have observed heads')
    lanes=set()
    for lane in report['lane_reports']:
        if (not fields(lane,'lane source_commit source_tree_sha256 cases')
                or not member(lane['lane'],LANES) or lane['lane'] in lanes
                or lane['source_commit'] != report['candidate_commit']
                or lane['source_tree_sha256'] != report['source_tree_sha256']
                or not isinstance(lane['cases'],list) or not lane['cases']):
            errors.append('invalid or stale lane report'); continue
        lanes.add(lane['lane']); seen=set()
        for case in lane['cases']:
            if (not fields(case,'case_id status') or not ident(case['case_id']) or case['case_id'] in seen
                    or not member(case['status'],('pass','fail','skipped','not_run'))):
                errors.append('invalid integration case'); continue
            seen.add(case['case_id'])
            if lane['lane'] in report['required_lanes'] and case['status'] != 'pass':
                errors.append('required lane did not pass')
        if lane['lane'] in report['required_lanes'] and (expected_cases is None or
                seen != expected_cases.get(lane['lane'])):
            errors.append('required lane case set differs from independent expectations')
    if not set(report['required_lanes']) <= lanes: errors.append('missing required lanes')
    return errors


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    parser.add_argument('--lane-directory',action='append',default=[],help='LANE=local bundle directory')
    parser.add_argument('--execution-lock',action='append',default=[],help='LANE=independently selected execution lock')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    try:
        report=json.loads(args.report.read_text())
        stack=json.loads((root/'docs/compatibility/stack-audit-v1.json').read_text())
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip()
        from run_validation import source_fingerprint
        from run_validation import steps
        clean=not bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=root))
        expected={lane:{name for name,_,_ in steps(lane,Path('validator'),Path('lock'))}
                  for lane in report.get('required_lanes',[]) if lane in ('cpu','validator','producer','arc','combined')}
        errors=validate_integration_report(report,stack,expected_candidate=head,expected_tree=source_fingerprint(root),
                                          expected_clean=clean,expected_cases=expected)
        from run_validation import validate_lane_bundle
        directories={}
        execution_locks={}
        for value in args.execution_lock:
            lane,path=value.split('=',1)
            if lane in execution_locks:raise ValueError('duplicate execution lock')
            execution_locks[lane]=json.loads(Path(path).read_text())
        for value in args.lane_directory:
            lane,path=value.split('=',1)
            if lane in directories:raise ValueError('duplicate lane directory')
            directories[lane]=Path(path)
        for lane in report.get('required_lanes',[]):
            if lane not in directories:
                errors.append('required original lane bundle missing');continue
            bundle_errors,original=validate_lane_bundle(directories[lane],root,lane,
                expected_commit=head,expected_tree=source_fingerprint(root),expected_clean=clean,
                expected_toolchain=execution_locks.get(lane))
            errors+=bundle_errors
            summary=next((x for x in report['lane_reports'] if x.get('lane')==lane),None)
            if original is not None and summary is not None and summary['cases']!=[
                    dict(case_id=c['case_id'],status=c['status']) for c in original['cases']]:
                errors.append('integration summary differs from original lane bundle')
    except (OSError,ValueError,subprocess.SubprocessError): errors=['integration inputs unavailable']
    for error in errors: print(error)
    if not errors: print('Integration identities match; actual execution is the runner responsibility.')
    return int(bool(errors))


if __name__=='__main__': raise SystemExit(main())
