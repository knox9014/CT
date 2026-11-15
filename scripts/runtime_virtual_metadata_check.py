"""Explicit software-target metadata; never a physical NVIDIA capability claim."""
import real_bootstrap_check as base
import runtime_metadata_check as previous
from export_reject_check import split
from primary_runtime_check import validate_states,validate_loader_metadata

POLICY='ct-sm52-subset-v1'
ATTRIBUTES=((75,0,5),(76,0,2),(15,801,0))


def expected_prefix(sample,name,total):
    return previous.expected_prefix(sample,name,total)[:-1]+[
        dict(kind='virtual_attribute_boundary' if attribute==15 else 'virtual_attribute_call',
             symbol='cuDeviceGetAttribute',attribute=attribute,ordinal=0,result=result,value=value)
        for attribute,result,value in ATTRIBUTES]


def validate(value):
    base.common(value,'ct_virtual_metadata_prefix',runtime=True);validate_loader_metadata(value);validate_states(value)
    if value.get('policy_mode')!=POLICY or value.get('policy_env_value')!=POLICY or value.get('software_target_only') is not True:
        raise ValueError('explicit software target required')
    name=value.get('name_control');memory=value.get('memory_control')
    if type(name) is not dict or set(name)!={'code','value'} or type(name['code']) is not int or name['code']!=0:raise ValueError('name control')
    if type(memory) is not dict or set(memory)!={'code','total_bytes'} or type(memory['code']) is not int or memory['code']!=0:raise ValueError('total control')
    sample=value.get('sample');total=memory['total_bytes'];text=name['value']
    previous.validate_prefix(previous.expected_prefix(sample,text,total),value['result'],sample,text,total)
    original=[];timeline=[]
    extra=('table_exposure','hooks_exposure','device_get_call','device_name_call','device_total_call','virtual_attribute_call','virtual_attribute_boundary')
    for row in value['prefix_trace']:
        if type(row) is not dict:raise ValueError('prefix row')
        kind=row.get('kind')
        if kind not in extra:original.append(row)
        if kind in ('call','intervention','export_rejection')+extra:timeline.append(row)
    original,_,surfaces=split(original);base.analyze(original)
    if len(surfaces)!=1 or value['patches']!=1 or timeline!=expected_prefix(sample,text,total):raise ValueError('virtual metadata order/surface')
    for row in timeline:
        for key in ('result','ordinal','attribute','length','byte_size','total_bytes'):
            if key in row and type(row[key]) is not int:raise ValueError('native scalar')
        if 'value' in row and row.get('kind')!='device_name_call' and type(row['value']) is not int:raise ValueError('native value scalar')
    return dict(runtime_code=3,actual_name=text,actual_total_bytes=total,actual_attribute=15,actual_attribute_code=801,
                virtual_major_minor=[5,2],policy_mode=POLICY,software_target_only=True,application_supported=False,shipping_version_authorized=False)


def validate_strict_control(value):
    if (type(value) is not dict or value.get('scope')!='ct_virtual_metadata_strict_control'
            or value.get('policy_env_absent') is not True or type(value.get('init_code')) is not int or value['init_code']!=0
            or value.get('application_supported') is not False or value.get('shipping_version_authorized') is not False):
        raise ValueError('strict control scope/policy')
    for key,expected in [('device_count',dict(code=0,value=1)),('attribute',dict(attribute=75,ordinal=0,result=801,value=0)),
                         ('actual_version',dict(code=801,value=0)),('primary_state',dict(code=0,flags=0,active=0))]:
        if not base.exact_ints(value.get(key),expected):raise ValueError('actual strict control changed')
    if not base.empty_context(value.get('current'),0):raise ValueError('strict current context')
