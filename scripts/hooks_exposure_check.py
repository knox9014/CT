"""Finite known-denial branch: actual Driver enumeration, private entry, Runtime3."""
import re
import real_bootstrap_check as base
from export_reject_check import split
from table_exposure_check import expected_prefix as previous_prefix
from table_exposure_observer import NEXT


def expected_prefix(sample):
    return previous_prefix(sample)[:-1]+[
        dict(kind='hooks_exposure',symbol='cuGetExportTable',uuid=NEXT,result=0,byte_size=56,fixture_kind='hooks_deny_only'),
        dict(kind='call',symbol='cuDeviceGetCount',result=0,value=1),
        dict(kind='device_get_call',symbol='cuDeviceGet',ordinal=0,result=0,value=0)]


def validate_prefix(trace,result,sample):
    if (type(sample) is not int or sample not in (12000,12090) or trace!=expected_prefix(sample)
            or any(type(r.get('result',0)) is not int for r in trace)
            or result!=dict(status='returned',code=3,value=-1) or type(result.get('code')) is not int or type(result.get('value')) is not int):
        raise ValueError('unreviewed hooks denial branch')
    for row in trace:
        for key in ('byte_size','ordinal','value'):
            if key in row and type(row[key]) is not int:raise ValueError('native scalar type')
    if trace[0]['output_cleared'] is not True:raise ValueError('early output not cleared')


def validate(value):
    base.common(value,'ct_hooks_deny_exposure',runtime=True)
    if type(value.get('fixture_sha256')) is not str or not re.fullmatch('[0-9a-f]{64}',value['fixture_sha256']):raise ValueError('fixture identity')
    original=[];timeline=[]
    for row in value['prefix_trace']:
        kind=row.get('kind')
        if kind not in ('table_exposure','hooks_exposure','device_get_call'):original.append(row)
        if kind in ('call','intervention','export_rejection','table_exposure','hooks_exposure','device_get_call'):timeline.append(row)
    original,_,surfaces=split(original);base.analyze(original)
    if len(surfaces)!=1 or value['patches']!=1:raise ValueError('surface role')
    validate_prefix(timeline,value['result'],value['sample'])
    if not base.exact_ints(value.get('fixture_before'),dict(mask=0,stopped=0,reserved=0)):raise ValueError('fixture not initially clear')
    for key in ('fixture_prefix','fixture_after_runtime'):
        if not base.exact_ints(value.get(key),dict(mask=2,stopped=1,reserved=0)):raise ValueError('wrong private callback or lifecycle')
    unload=value.get('fixture_unload')
    if type(unload) is not dict or set(unload)!={'free_succeeded','module_absent'} or any(v is not True for v in unload.values()):raise ValueError('fixture remains loaded')
    if not base.empty_context(value.get('context_after'),0):raise ValueError('context left current')
    return dict(runtime_code=3,actual_driver_count=1,device_ordinal=0,private_context_entry_mask=2,hooks_getters_called=False,
                application_supported=False,shipping_version_authorized=False)
