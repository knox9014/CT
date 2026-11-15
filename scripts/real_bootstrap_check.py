"""Real-provider counterfactual evidence, never shipping/version/app qualification."""
import re
from runtime_bootstrap_contract import classify,integer

def exact_ints(data,wanted):
    return type(data) is dict and set(data)==set(wanted) and all(type(data[k]) is int and data[k]==v for k,v in wanted.items())

def empty_context(value,code):
    return (type(value) is dict and set(value)=={'code','is_null'} and type(value['code']) is int
            and value['code']==code and value['is_null'] is True)

def analyze(trace,*,allow_guards=False):
    if type(trace) is not list or len(trace)>4096:raise ValueError('trace scope')
    calls=[];interventions=[];guards=[]
    for row in trace:
        if type(row) is not dict:raise ValueError('trace row')
        kind=row.get('kind')
        if kind in ('lookup','resolver_v1','resolver_v2'):
            classify([row])
        elif kind=='call':
            if row.get('symbol')=='cuDeviceGetCount':
                if (set(row)!={'kind','symbol','result','value'} or not integer(row['result'])
                        or row['value'] is not None and not integer(row['value'],-2**31)):raise ValueError('count call')
            else:classify([row])
            calls.append(row)
        elif kind=='intervention':
            if (set(row)!={'kind','symbol','original_result','original_value','presented_result','presented_value'}
                    or row['symbol']!='cuDriverGetVersion' or any(type(row[k]) is not int for k in ('original_result','original_value','presented_result','presented_value'))
                    or (row['original_result'],row['original_value'],row['presented_result'])!=(801,0,0)
                    or row['presented_value'] not in (12000,12090)):
                raise ValueError('presentation differs from recorded actual call')
            if not calls or calls[-1]!=dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0):raise ValueError('presentation without actual version call')
            interventions.append(row)
        elif kind=='guard' and allow_guards:
            if (set(row)!={'kind','symbol','result','output_cleared'} or type(row['result']) is not int or row['result']!=801
                    or row['symbol'] not in ('cuModuleLoadData','cuLaunchKernel') or type(row['output_cleared']) is not bool):raise ValueError('guard contract row')
            if row['output_cleared']!=(row['symbol']=='cuModuleLoadData'):raise ValueError('module output not cleared')
            guards.append(row)
        else:raise ValueError('callback failure/guard/unreviewed event')
    return calls,interventions,guards

def common(value,scope,*,runtime,contract=False):
    if (type(value) is not dict or value.get('scope')!=scope or value.get('application_supported') is not False
            or value.get('shipping_version_authorized') is not False or value.get('restored') is not True
            or value.get('restore_error') is not None or value.get('callback_failures')!=[] or value.get('blocked_callbacks')!=[]
            or not integer(value.get('patches'))):raise ValueError('evidence role/restoration/failure')
    if not exact_ints(value.get('actual_version_before'),dict(code=801,value=0)) or not exact_ints(value.get('actual_version_after'),dict(code=801,value=0)):
        raise ValueError('real product version changed')
    if not contract and value.get('guard_hits')!=[]:raise ValueError('unexpected guard hit')
    if runtime:
        unload=value.get('runtime_unload')
        if type(unload) is not dict or set(unload)!={'free_succeeded','module_absent'} or any(unload[k] is not True for k in unload):raise ValueError('owned Runtime remains loaded')
    elif value.get('runtime_unload') is not None:raise ValueError('unexpected Runtime loading')
    analyze(value.get('teardown_trace'),allow_guards=contract)

def baseline(value,*,faithful):
    common(value,'ct_guarded_observation' if faithful else 'ct_nominal',runtime=True)
    if value.get('sample') is not None or value['result']!=dict(status='returned',code=35,value=-1):raise ValueError('baseline changed')
    calls,interventions,guards=analyze(value['prefix_trace'])
    if interventions or guards or calls!=([dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0)] if faithful else []):raise ValueError('baseline call sequence')
    if faithful and value['patches']<1 or not faithful and value['patches']!=0:raise ValueError('baseline observer role')
    if not empty_context(value.get('context_after'),3):raise ValueError('baseline unexpectedly initialized')

def ordinary(value):
    common(value,'ct_direct',runtime=False)
    if value.get('sample') is not None or value['prefix_trace']!=[] or value['patches']!=0:raise ValueError('ordinary Driver was instrumented')
    row=value['result']
    wanted=dict(init_code=0,count_code=0,null_version=1,before_code=3,before_value=-1,before_null=3,invalid_init=1,after_null=1,name_code=0)
    if any(type(row.get(k)) is not int or row[k]!=v for k,v in wanted.items()):raise ValueError('actual Driver init/error contract')
    if not integer(row.get('count'),1,4096):raise ValueError('real device count')
    if type(row.get('device_name')) is not str or not re.fullmatch(r'Intel[^\r\n]{0,240}',row['device_name']):raise ValueError('unexpected device identity')
    if not empty_context(row.get('context'),0) or not empty_context(value.get('context_after'),0):raise ValueError('unexpected CUDA context')
    return row['count']

def counterfactual(value,direct_count):
    common(value,'ct_guarded_counterfactual',runtime=True)
    sample=value.get('sample')
    if type(sample) is not int or sample not in (12000,12090) or value['patches']<1:raise ValueError('fixed sample/observer')
    calls,interventions,_=analyze(value['prefix_trace'])
    if len(interventions)!=1 or interventions[0]['presented_value']!=sample:raise ValueError('wrong presented sample')
    expected=[dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0),dict(kind='call',symbol='cuInit',flags=0,result=0)]
    if calls[:2]!=expected:raise ValueError('real init did not succeed')
    outcome=value['result']
    if (set(outcome)!={'status','code','value'} or outcome['status']!='returned' or not integer(outcome['code'])
            or not integer(outcome['value'],-2**31) or not integer(direct_count,1,4096)):raise ValueError('native fault/outcome')
    # Equality alone would accept booleans, so validate every actual-call scalar first.
    for row in calls:
        if type(row['result']) is not int:raise ValueError('actual status type')
    if outcome['code']==0:
        if calls!=expected+[dict(kind='call',symbol='cuDeviceGetCount',result=0,value=direct_count)] or outcome['value']!=direct_count:
            raise ValueError('Runtime enumeration lacks unchanged actual count')
    elif outcome['code']!=36 or calls!=expected or outcome['value']!=-1:
        raise ValueError('unreviewed error path; preserve for investigation')
    if not empty_context(value.get('context_after'),0):raise ValueError('CUDA context left current')
    return dict(application_supported=False,shipping_version_authorized=False,sample=sample,real_init_passed=True,
                runtime_code=outcome['code'],runtime_enumeration_passed=outcome['code']==0,
                actual_count_calls=len(calls)-2,required_missing_api_identified=False)

def guard_contract(value):
    common(value,'ct_guard_contract',runtime=False,contract=True)
    calls,interventions,guards=analyze(value['prefix_trace'],allow_guards=True)
    if value.get('sample') is not None or value['patches']!=0 or not exact_ints(value['result'],dict(checks=20)):
        raise ValueError('guard contract role/check count')
    expected=[dict(kind='call',symbol='cuDriverGetVersion',result=1,value=None),
              dict(kind='call',symbol='cuDeviceGetCount',result=3,value=-1),dict(kind='call',symbol='cuDeviceGetCount',result=3,value=None),
              dict(kind='call',symbol='cuInit',flags=1,result=1)]
    if calls!=expected or interventions or len(guards)!=6 or guards!=value['guard_hits']:raise ValueError('guard ABI checks changed')
    if [x['symbol'] for x in guards]!=['cuModuleLoadData','cuLaunchKernel']*3:raise ValueError('guard lookup routes')
    if not empty_context(value.get('context_after'),3):raise ValueError('guard contract initialized backend')
