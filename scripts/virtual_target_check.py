"""Closed evidence contracts for the actual experimental product target."""
from matrix_runtime_check import exact
from matrix_runtime_check import SHAPES,buffers_valid,expected_output
import struct

TARGET='ct-sm52-subset-v1'
QUALIFICATION=dict(experimental=True,virtual_target=TARGET,metadata_injected=False,
                   nvidia_hardware_claim=False,general_application_compatibility=False,release_claim=False)
ABI_MODES=('strict_rt_first','strict_driver_first','virtual_rt_first','virtual_driver_first','flags','invalid','empty','nonunicode')

def qualification_valid(value):return exact(value,QUALIFICATION)

def abi_valid(mode,value):
    if mode=='loader':return exact(value,dict(status='pass',loader_error=35))
    if mode in ('invalid','empty','nonunicode'):return exact(value,dict(status='pass',invalid_config=1))
    if mode not in ABI_MODES:return False
    virtual=mode.startswith('virtual') or mode=='flags'
    return exact(value,dict(status='pass',virtual=virtual,major=5 if virtual else 0,minor=2 if virtual else 0,
                           context_unchanged=True,physical_intel=True,policy_immutable=True,
                           late_unsupported_rejected=virtual))

def trace_valid(value,mode):
    if mode not in ('trace','noop_launch','noop_copy'):return False
    return exact(value,dict(allocations=3,h2d=2,dtoh=1,launches=301,
                           forwarded=0 if mode=='noop_launch' else 301,frees=3,
                           uploaded=0 if mode=='noop_copy' else 2,metadata_injected=False))

def app_valid(mode,shape,code,stdout,stderr,a=None,b=None,c=None,trace=None):
    if shape not in SHAPES or type(code) is not int:return False
    if mode in ('strict','invalid_config'):
        token=b'cudaErrorNotSupported' if mode=='strict' else b'cudaErrorInvalidValue'
        call=b'cudaDevAttrComputeCapabilityMajor' if mode=='strict' else b'cudaGetDeviceCount'
        return code==1 and token in stderr and call in stderr
    if mode not in ('nominal','trace','noop_launch','noop_copy') or code!=0 or stderr or b'Result = PASS' not in stdout:return False
    if mode=='nominal':return a is None and b is None and c is None and trace is None
    if not trace_valid(trace,mode):return False
    if mode=='trace':return buffers_valid(shape,a,b,c)
    if not buffers_valid(shape,a,b,expected_output(shape)) or len(c)!=shape[0]*shape[2]*4:return False
    if any((v[0]&0x7f800000)!=0x7f800000 or not(v[0]&0x7fffff) for v in struct.iter_unpack('<I',c)):return False
    return mode=='noop_copy' or c==struct.pack('<I',0x7fc00000)*(shape[0]*shape[2])
