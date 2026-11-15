"""Independent closed oracle for opt-in maximum-topology metadata, not SMs."""
import re
from matrix_runtime_check import exact

TOPOLOGY_POLICY=dict(attribute=16,strict_result=801,
    source='Level Zero maximum numSlices and numSubslicesPerSlice',
    mapping='checked positive maximum-dimension product fitting i32',
    meaning='CT software-target topology count, not active NVIDIA SMs, Intel EUs or occupancy',
    invalid_result=801)
TOPOLOGY_MODES=('strict_rt_first','strict_driver_first','virtual_rt_first','virtual_driver_first','minimal_strict','minimal_virtual','missing','forwarded','absent')


def topology_valid(mode,value):
    if mode in ('missing','forwarded','absent'):return exact(value,dict(status='pass',loader_error=35))
    if mode not in TOPOLOGY_MODES or type(value) is not dict:return False
    slices=value.get('max_slices');subslices=value.get('max_subslices_per_slice')
    if any(type(x) is not int or not 1<=x<=2**32-1 for x in (slices,subslices)):return False
    count=slices*subslices
    if count>2**31-1:return False
    name=value.get('device_name')
    if type(name) is not str or not re.fullmatch(r'Intel[^\r\n]{0,240}',name):return False
    virtual=mode.startswith('virtual') or mode=='minimal_virtual'
    return exact(value,dict(status='pass',virtual=virtual,device_name=name,max_slices=slices,max_subslices_per_slice=subslices,topology_count=count,
                           driver_code=0 if virtual else 801,driver_value=count if virtual else 0,
                           runtime_code=0 if virtual else 801,runtime_value=count if virtual else 456,
                           identity_unique=True,snapshot_stable=True,context_unchanged=True,policy_immutable=True,
                           physical_intel=True,maxima_only=True,nvidia_sm_claim=False))
