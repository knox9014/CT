"""One successful native context followed by a finite name-query stop."""
import real_bootstrap_check as base
from export_reject_check import split
from hooks_exposure_check import expected_prefix as previous_prefix


def expected_prefix(sample):
    rows=previous_prefix(sample)
    rows[4]=dict(rows[4],fixture_kind='cudart_native_context_only')
    return rows+[dict(kind='next_public_boundary',symbol='cuDeviceGetName',length=256,ordinal=0,result=801,output_cleared=True)]


def validate_prefix(trace,result,sample):
    if (type(sample) is not int or sample not in (12000,12090) or trace!=expected_prefix(sample)
            or result!=dict(status='returned',code=3,value=-1)
            or type(result.get('code')) is not int or type(result.get('value')) is not int):raise ValueError('unreviewed native-context prefix')
    for row in trace:
        for key in ('result','value','ordinal','length','byte_size'):
            if key in row and type(row[key]) is not int:raise ValueError('native scalar type')
    if trace[0]['output_cleared'] is not True or trace[-1]['output_cleared'] is not True:raise ValueError('uncleared boundary')


def validate_states(value):
    for key in ('deny_before','deny_prefix','deny_after_runtime'):
        if not base.exact_ints(value.get(key),dict(mask=0,stopped=0,reserved=0)):raise ValueError('private denial hit')
    for key,expected in [('native_before',dict(calls=0,result=0,nonnull=0)),
                         ('native_prefix',dict(calls=1,result=0,nonnull=1)),('native_after_runtime',dict(calls=1,result=0,nonnull=1))]:
        if not base.exact_ints(value.get(key),expected):raise ValueError('wrong native context callback')
    for key in ('primary_before_reset','primary_after_reset'):
        if not base.exact_ints(value.get(key),dict(code=0,flags=0,active=0)):raise ValueError('wrong primary lifetime state')
    if type(value.get('primary_reset_code')) is not int or value['primary_reset_code']!=0:raise ValueError('reservation cleanup failed')
    if not base.empty_context(value.get('current_after_reset'),0):raise ValueError('current context changed')


def validate_loader_metadata(value):
    if value.get('state_failures')!=[]:raise ValueError('intermediate CUDA state failure')
    foreign=value.get('foreign_lookups')
    if type(foreign) is not list or len(foreign)>4096:raise ValueError('foreign loader metadata')
    for row in foreign:
        if (type(row) is not dict or set(row)!={'symbol','phase','native'} or type(row['symbol']) is not str
                or len(row['symbol'])>256 or type(row['phase']) is not int or row['phase'] not in range(4)
                or not any(base.exact_ints(row['native'],v) for v in (dict(calls=0,result=0,nonnull=0),dict(calls=1,result=0,nonnull=0),dict(calls=1,result=0,nonnull=1)))):
            raise ValueError('unreviewed foreign loader event')


def validate(value):
    base.common(value,'ct_primary_runtime_bridge',runtime=True)
    validate_loader_metadata(value)
    original=[];timeline=[]
    for row in value['prefix_trace']:
        kind=row.get('kind')
        if kind not in ('table_exposure','hooks_exposure','device_get_call','next_public_boundary'):original.append(row)
        if kind in ('call','intervention','export_rejection','table_exposure','hooks_exposure','device_get_call','next_public_boundary'):timeline.append(row)
    original,_,surfaces=split(original);base.analyze(original)
    if len(surfaces)!=1 or value['patches']!=1:raise ValueError('surface role')
    validate_prefix(timeline,value['result'],value['sample']);validate_states(value)
    return dict(runtime_code=3,private_context_calls=1,private_context_result=0,real_driver_count=1,
                next_boundary='cuDeviceGetName',private_runtime_prefix_connected=True,application_supported=False)
