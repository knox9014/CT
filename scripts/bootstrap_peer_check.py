"""Synthetic experiment contracts, intentionally separate from nominal CT checks."""
import re
RESPONSES=((801,0),(0,0),(0,11000),(0,12000),(0,12090))
SURFACE={'cuInit','cuDriverGetVersion','cuGetExportTable','cuGetProcAddress'}

def integer(value,lo=-2**31,hi=2**31-1):return type(value) is int and lo<=value<=hi

def validate_trial(value):
    fields={'scope','application_supported','mode','trace_enabled','outcome','trace','overflow','provider_sha256','runtime_sha256'}
    if (type(value) is not dict or set(value)!=fields or value['scope']!='synthetic_intervention'
            or value['application_supported'] is not False or value['overflow'] is not False
            or not integer(value['mode'],0,4) or type(value['trace_enabled']) is not bool):raise ValueError('synthetic scope')
    for key in ('provider_sha256','runtime_sha256'):
        if type(value[key]) is not str or not re.fullmatch('[0-9a-f]{64}',value[key]):raise ValueError('peer identity')
    outcome=value['outcome'];mode=value['mode']
    if (type(outcome) is not dict or set(outcome)!={'status','code','count'} or outcome['status']!='returned'
            or not integer(outcome['code']) or outcome['code']!=(35 if mode<3 else 801)
            or type(outcome['count']) is not int or outcome['count']!=-1):raise ValueError('unexpected/native-fault prefix outcome')
    trace=value['trace']
    if type(trace) is not list or len(trace)>512 or (not value['trace_enabled'] and trace):raise ValueError('trace scope')
    calls=[];tables=[]
    for row in trace:
        if type(row) is not dict or set(row)!={'kind','symbol','version','flags','result','status','found','value','uuid'}:raise ValueError('peer row shape')
        if (not integer(row['kind'],1,5) or not integer(row['version']) or not integer(row['flags'],0,2**64-1)
                or not integer(row['result'],0) or not integer(row['status'],-1,2) or not integer(row['found'],0,1)
                or not integer(row['value']) or type(row['symbol']) is not str
                or not re.fullmatch(r'(?:[A-Za-z_][A-Za-z_0-9]{0,62}|<null>)?',row['symbol'])
                or type(row['uuid']) is not str or not re.fullmatch('[0-9a-f]{32}',row['uuid'])):raise ValueError('peer row type/range')
        kind=row['kind'];symbol=row['symbol']
        if kind<=2:
            if row['found'] and (symbol not in SURFACE or row['result']!=0):raise ValueError('unexpected callable surface')
            if row['status']>=0 and row['result']==0 and (row['status']==0)!=(row['found']==1):raise ValueError('peer status/pointer mismatch')
        else:
            calls.append(symbol)
            if row['version']!=0 or row['status']!=-1 or row['found']!=0:raise ValueError('actual call metadata')
            if kind==3:
                if symbol!='cuDriverGetVersion' or (row['result'],row['value'])!=RESPONSES[mode] or row['flags']!=0:raise ValueError('sample response changed')
            elif kind==4:
                if symbol!='cuInit' or row['flags']!=0 or row['result']!=801:raise ValueError('init guard bypass')
            elif kind==5:
                if symbol!='cuGetExportTable' or row['result']!=801 or row['flags']!=0:raise ValueError('private table fabricated')
                tables.append(row['uuid'])
    expected=['cuGetExportTable','cuDriverGetVersion']+(['cuInit'] if mode>=3 else [])
    if value['trace_enabled'] and calls!=expected:raise ValueError('unexpected actual call order')
    return dict(scope='synthetic_intervention',application_supported=False,ct_compatibility_inferred=False,
                init_attempted=(mode>=3) if value['trace_enabled'] else None,observed_call_order=calls,
                opaque_table_ids=tables,outcome=outcome)

def compare_pair(traced,untraced):
    result=validate_trial(traced);validate_trial(untraced)
    if (not traced['trace_enabled'] or untraced['trace_enabled'] or traced['mode']!=untraced['mode']
            or traced['provider_sha256']!=untraced['provider_sha256'] or traced['runtime_sha256']!=untraced['runtime_sha256']
            or traced['outcome']!=untraced['outcome']):raise ValueError('tracing-off control changed')
    return dict(result,tracing_control_matches=True)
