"""Exact actual scheduling prefix and a single observed unsupported query."""
import real_bootstrap_check as base
import runtime_metadata_check as metadata
from export_reject_check import split
from primary_runtime_check import validate_states,validate_loader_metadata
from runtime_virtual_metadata_check import POLICY,validate_strict_control
from scheduling_pointer_guards import FORWARDED,GUARDED

PREFIX=((75,0,5),(76,0,2),(15,0,0),(40,0,0))
SUPPORTED=frozenset((*range(1,9),15,20,40,75,76))


def boundary_attribute(attribute):
    return type(attribute) is int and 1<=attribute<=255 and attribute not in SUPPORTED


def expected_prefix(sample,name,total,boundary):
    return metadata.expected_prefix(sample,name,total)[:-1]+[
        dict(kind='scheduling_attribute_call',symbol='cuDeviceGetAttribute',attribute=a,ordinal=0,result=r,value=v)
        for a,r,v in PREFIX]+[dict(kind='scheduling_attribute_boundary',symbol='cuDeviceGetAttribute',attribute=boundary,ordinal=0,result=801,value=0)]


def validate(value):
    base.common(value,'ct_scheduling_metadata_prefix',runtime=True);validate_loader_metadata(value);validate_states(value)
    if not base.empty_context(value.get('context_after'),0):raise ValueError('post-unload current context')
    if value.get('policy_mode')!=POLICY or value.get('policy_env_value')!=POLICY or value.get('software_target_only') is not True:
        raise ValueError('explicit software target required')
    name=value.get('name_control');memory=value.get('memory_control');boundary=value.get('boundary_control')
    if type(name) is not dict or set(name)!={'code','value'} or type(name['code']) is not int or name['code']!=0:raise ValueError('name control')
    if type(memory) is not dict or set(memory)!={'code','total_bytes'} or type(memory['code']) is not int or memory['code']!=0:raise ValueError('total control')
    if type(boundary) is not dict or not boundary_attribute(boundary.get('attribute')):raise ValueError('boundary attribute')
    attribute=boundary['attribute']
    if not base.exact_ints(boundary,dict(attribute=attribute,ordinal=0,result=801,value=0)):raise ValueError('boundary control')
    controls=value.get('scheduling_controls')
    if type(controls) is not list or len(controls)!=2:raise ValueError('scheduling controls')
    for row,a in zip(controls,(15,40)):
        if not base.exact_ints(row,dict(attribute=a,ordinal=0,result=0,value=0)):raise ValueError('actual scheduling control')
    sample=value.get('sample');total=memory['total_bytes'];text=name['value']
    metadata.validate_prefix(metadata.expected_prefix(sample,text,total),value['result'],sample,text,total)
    original=[];timeline=[];resolved=set();guards=set();previous=None;pending=None
    extra=('table_exposure','hooks_exposure','device_get_call','device_name_call','device_total_call','scheduling_attribute_call','scheduling_attribute_boundary','scheduling_guard_binding')
    for row in value['prefix_trace']:
        if type(row) is not dict:raise ValueError('prefix row')
        kind=row.get('kind')
        if pending is not None:
            if kind!='scheduling_guard_binding' or row.get('symbol')!=pending:raise ValueError('first guard exposure order')
            pending=None
        if kind in ('lookup','resolver_v1','resolver_v2') and row.get('found') is True:
            symbol=row.get('symbol')
            if symbol not in FORWARDED:
                if symbol not in GUARDED:raise ValueError('unwrapped resolved symbol')
                resolved.add(symbol)
                if symbol not in guards:pending=symbol
        if kind=='scheduling_guard_binding':
            symbol=row.get('symbol')
            if (set(row)!={'kind','symbol'} or symbol not in GUARDED or symbol in guards or previous is None
                    or previous.get('kind') not in ('lookup','resolver_v1','resolver_v2')
                    or previous.get('found') is not True or previous.get('symbol')!=symbol):raise ValueError('guard binding evidence')
            guards.add(symbol)
        if kind not in extra:original.append(row)
        if kind in ('call','intervention','export_rejection')+extra and kind!='scheduling_guard_binding':timeline.append(row)
        previous=row
    if resolved!=guards:raise ValueError('missing guard binding evidence')
    original,_,surfaces=split(original);base.analyze(original)
    if len(surfaces)!=1 or value['patches']!=1 or timeline!=expected_prefix(sample,text,total,attribute):raise ValueError('scheduling order/surface')
    for row in timeline:
        for key in ('result','ordinal','attribute','length','byte_size','total_bytes'):
            if key in row and type(row[key]) is not int:raise ValueError('native scalar')
        if 'value' in row and row.get('kind')!='device_name_call' and type(row['value']) is not int:raise ValueError('native value scalar')
    return dict(runtime_code=3,actual_name=text,actual_total_bytes=total,actual_attribute=attribute,actual_attribute_code=801,
                actual_overlap=0,actual_async_engines=0,virtual_major_minor=[5,2],policy_mode=POLICY,software_target_only=True,
                application_supported=False,shipping_version_authorized=False)
