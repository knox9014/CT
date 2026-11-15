"""Exact finite CUDART pointer presentation and next-query evidence."""
import re
from export_reject_check import split
from export_reject_observer import IDS
from table_exposure_observer import NEXT
import real_bootstrap_check as base


def expected_prefix(sample):
    return [dict(kind='export_rejection',symbol='cuGetExportTable',uuid=IDS[0],result=801,output_cleared=True),
            dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0),
            dict(kind='intervention',symbol='cuDriverGetVersion',original_result=801,original_value=0,presented_result=0,presented_value=sample),
            dict(kind='call',symbol='cuInit',flags=0,result=0),
            dict(kind='table_exposure',symbol='cuGetExportTable',uuid=IDS[1],result=0,byte_size=104,fixture_kind='cudart_deny_only'),
            dict(kind='known_next_rejection',symbol='cuGetExportTable',uuid=NEXT,result=801,output_cleared=True)]


def validate_prefix(trace,result,sample):
    if (type(sample) is not int or sample not in (12000,12090) or trace!=expected_prefix(sample)
            or any(type(r.get('result',0)) is not int for r in trace)
            or result!=dict(status='returned',code=801,value=-1) or type(result.get('code')) is not int or type(result.get('value')) is not int):
        raise ValueError('unexpected exposure prefix/outcome')
    if trace[0]['output_cleared'] is not True or trace[-1]['output_cleared'] is not True or type(trace[-2]['byte_size']) is not int:
        raise ValueError('exposure field types')


def validate(value):
    base.common(value,'ct_cudart_table_exposure',runtime=True)
    if type(value.get('fixture_sha256')) is not str or not re.fullmatch('[0-9a-f]{64}',value['fixture_sha256']):raise ValueError('missing fixture identity')
    trace=value['prefix_trace'];remaining=[];timeline=[]
    for row in trace:
        if row.get('kind') not in ('table_exposure','known_next_rejection'):remaining.append(row)
        if row.get('kind') in ('call','intervention','export_rejection','table_exposure','known_next_rejection'):timeline.append(row)
    original,_,surfaces=split(remaining);base.analyze(original)
    if len(surfaces)!=1 or value['patches']!=1:raise ValueError('surface role')
    validate_prefix(timeline,value['result'],value['sample'])
    for key in ('fixture_before','fixture_prefix','fixture_after_runtime'):
        if not base.exact_ints(value.get(key),dict(mask=0,stopped=0,reserved=0)):raise ValueError('private callback/lifecycle')
    unload=value.get('fixture_unload')
    if type(unload) is not dict or set(unload)!={'free_succeeded','module_absent'} or any(v is not True for v in unload.values()):raise ValueError('fixture remains loaded')
    if not base.empty_context(value.get('context_after'),0):raise ValueError('context left current')
    return dict(runtime_code=801,export_queries=3,private_callback_mask=0,next_query=NEXT,application_supported=False,shipping_version_authorized=False)
