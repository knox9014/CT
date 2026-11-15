"""Actual metadata queries followed by the default strict-capability refusal."""
import re
import real_bootstrap_check as base
from export_reject_check import split
from primary_runtime_check import expected_prefix as previous_prefix,validate_states,validate_loader_metadata


def expected_prefix(sample,name,total):
    return previous_prefix(sample)[:-1]+[
        dict(kind='device_name_call',symbol='cuDeviceGetName',length=256,ordinal=0,result=0,value=name),
        dict(kind='device_total_call',symbol='cuDeviceTotalMem',ordinal=0,result=0,total_bytes=total),
        dict(kind='strict_attribute_boundary',symbol='cuDeviceGetAttribute',attribute=75,ordinal=0,result=801,value=0)]


def validate_prefix(trace,result,sample,name,total):
    if (type(sample) is not int or sample not in (12000,12090) or type(name) is not str or not re.fullmatch(r'Intel[^\r\n]{0,240}',name)
            or type(total) is not int or not 0<total<2**64 or trace!=expected_prefix(sample,name,total)
            or result!=dict(status='returned',code=3,value=-1) or type(result.get('code')) is not int or type(result.get('value')) is not int):raise ValueError('unreviewed metadata prefix')
    for row in trace:
        for key in ('result','ordinal','attribute','length','byte_size','total_bytes'):
            if key in row and type(row[key]) is not int:raise ValueError('native metadata scalar')
        if row.get('kind')!='device_name_call' and 'value' in row and type(row['value']) is not int:raise ValueError('native value type')
    if trace[0]['output_cleared'] is not True:raise ValueError('early output not cleared')


def validate(value):
    base.common(value,'ct_runtime_metadata_prefix',runtime=True);validate_loader_metadata(value);validate_states(value)
    if value.get('policy_mode')!='strict-default' or value.get('policy_env_absent') is not True:raise ValueError('non-strict policy inherited')
    name=value.get('name_control');memory=value.get('memory_control')
    if type(name) is not dict or set(name)!={'code','value'} or type(name['code']) is not int or name['code']!=0:raise ValueError('name control failed')
    if type(memory) is not dict or set(memory)!={'code','total_bytes'} or type(memory['code']) is not int or memory['code']!=0:raise ValueError('memory control failed')
    original=[];timeline=[]
    extra=('table_exposure','hooks_exposure','device_get_call','device_name_call','device_total_call','strict_attribute_boundary')
    for row in value['prefix_trace']:
        kind=row.get('kind')
        if kind not in extra:original.append(row)
        if kind in ('call','intervention','export_rejection')+extra:timeline.append(row)
    original,_,surfaces=split(original);base.analyze(original)
    if len(surfaces)!=1 or value['patches']!=1:raise ValueError('surface role')
    validate_prefix(timeline,value['result'],value['sample'],name['value'],memory['total_bytes'])
    return dict(runtime_code=3,private_context_calls=1,actual_name=name['value'],actual_total_bytes=memory['total_bytes'],
                actual_attribute=75,actual_attribute_code=801,policy_mode='strict-default',application_supported=False,shipping_version_authorized=False)
