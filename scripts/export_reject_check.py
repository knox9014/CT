"""Finite rejection evidence: preserve actual results and label added surface."""
import copy
from export_reject_observer import IDS
import real_bootstrap_check as base


def reject_prefix(trace,result,sample):
    if type(sample) is not int or sample not in (12000,12090):raise ValueError('fixed sample')
    expected=[dict(kind='export_rejection',symbol='cuGetExportTable',uuid=IDS[0],result=801,output_cleared=True),
              dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0),
              dict(kind='intervention',symbol='cuDriverGetVersion',original_result=801,original_value=0,presented_result=0,presented_value=sample),
              dict(kind='call',symbol='cuInit',flags=0,result=0),
              dict(kind='export_rejection',symbol='cuGetExportTable',uuid=IDS[1],result=801,output_cleared=True)]
    if (trace!=expected or type(trace) is not list or any(type(row.get('result',0)) is not int for row in trace)
            or type(result) is not dict or result!=dict(status='returned',code=801,value=-1)
            or type(result.get('code')) is not int or type(result.get('value')) is not int):
        raise ValueError('unreviewed rejection order/outcome')


def split(trace):
    if type(trace) is not list or len(trace)>4096:raise ValueError('trace scope')
    original=[];prefix=[];surfaces=[]
    for index,row in enumerate(trace):
        if type(row) is not dict:raise ValueError('trace row')
        kind=row.get('kind')
        if kind=='export_surface_intervention':
            expected=dict(kind=kind,symbol='cuGetExportTable',version=3000,flags=0,original_result=0,original_found=False,
                          original_status=row.get('original_status'),presented_result=0,presented_found=True,
                          presented_status=0 if row.get('original_status') is not None else None)
            if row!=expected or row['original_status'] not in (None,1):raise ValueError('surface metadata')
            if not index or trace[index-1]!=dict(kind='resolver_v2',symbol='cuGetExportTable',version=3000,flags=0,
                                                result=0,status=row['original_status'],found=False):raise ValueError('surface lacks actual lookup')
            if any(type(row[k]) is not int for k in ('version','flags','original_result','presented_result')):raise ValueError('surface scalar type')
            if row['original_found'] is not False or row['presented_found'] is not True:raise ValueError('surface found flags')
            if row['original_status'] is not None and type(row['original_status']) is not int:raise ValueError('surface status type')
            if row['presented_status'] is not None and type(row['presented_status']) is not int:raise ValueError('presented status type')
            surfaces.append(row)
        elif kind=='export_rejection':
            if not surfaces:raise ValueError('query before surface presentation')
            if (set(row)!={'kind','symbol','uuid','result','output_cleared'} or row['symbol']!='cuGetExportTable'
                    or type(row['result']) is not int or type(row['output_cleared']) is not bool):raise ValueError('export event')
            prefix.append(row)
        else:
            original.append(row)
            if kind in ('call','intervention'):prefix.append(row)
    base.analyze(original,allow_guards=True)
    return original,prefix,surfaces


def rejection(value):
    base.common(value,'ct_export_rejection',runtime=True)
    original,prefix,surfaces=split(value['prefix_trace'])
    base.analyze(original)
    if len(surfaces)!=1 or value.get('patches')!=1:raise ValueError('surface scope')
    reject_prefix(prefix,value['result'],value.get('sample'))
    if not base.empty_context(value.get('context_after'),0):raise ValueError('context left current')
    return dict(runtime_code=801,export_calls=2,real_init_passed=True,application_supported=False,shipping_version_authorized=False)


def contract(value):
    base.common(value,'ct_export_contract',runtime=False,contract=True)
    original,prefix,surfaces=split(value['prefix_trace'])
    view=copy.deepcopy(value);view['scope']='ct_guard_contract';view['prefix_trace']=original;view['result']=dict(checks=20)
    base.guard_contract(view)
    if not base.exact_ints(value['result'],dict(checks=31)) or len(surfaces)!=1:raise ValueError('export contract checks')
    queries=[r for r in prefix if r['kind']=='export_rejection']
    expected=[dict(kind='export_rejection',symbol='cuGetExportTable',uuid=uuid,result=801,output_cleared=True) for uuid in IDS]
    expected.extend([dict(kind='export_rejection',symbol='cuGetExportTable',uuid=None,result=1,output_cleared=False),
                     dict(kind='export_rejection',symbol='cuGetExportTable',uuid=None,result=1,output_cleared=True)])
    if queries!=expected:raise ValueError('export argument contract')
