"""CT header signatures for diagnostic deny-only pointer wrappers, never execution."""
import ctypes as c

V=c.c_void_p;P=c.POINTER(V);I=c.c_int;U=c.c_uint;D=c.c_uint64;S=c.c_size_t
IP=c.POINTER(I);UP=c.POINTER(U);DP=c.POINTER(D);SP=c.POINTER(S)
FORWARDED=frozenset(('cuInit','cuDriverGetVersion','cuGetProcAddress','cuGetProcAddress_v2','cuDeviceGetCount',
    'cuDeviceGet','cuDeviceGetName','cuDeviceTotalMem','cuDeviceTotalMem_v2','cuDeviceGetAttribute','cuModuleLoadData','cuLaunchKernel'))
GUARDED={
    'cuDevicePrimaryCtxRetain':(P,I),
    'cuDevicePrimaryCtxSetFlags':(I,U),
    'cuDevicePrimaryCtxReset':(I,),
    'cuDevicePrimaryCtxGetState':(I,UP,IP),
    'cuDevicePrimaryCtxRelease':(I,),
    'cuCtxGetFlags':(UP,),
    'cuCtxCreate':(P,U,I),
    'cuCtxDestroy':(V,),
    'cuCtxGetCurrent':(P,),
    'cuCtxSetCurrent':(V,),
    'cuCtxPushCurrent':(V,),
    'cuCtxPopCurrent':(P,),
    'cuCtxGetDevice':(IP,),
    'cuCtxSynchronize':(),
    'cuMemAlloc':(DP,S),
    'cuMemFree':(D,),
    'cuMemHostAlloc':(P,S,U),
    'cuMemFreeHost':(V,),
    'cuMemGetAddressRange':(DP,SP,D),
    'cuPointerGetAttribute':(V,I,D),
    'cuMemcpyHtoD':(D,V,S),
    'cuMemcpyDtoH':(V,D,S),
    'cuMemcpyDtoD':(D,D,S),
    'cuMemsetD8':(D,c.c_ubyte,S),
    'cuMemsetD16':(D,c.c_ushort,S),
    'cuMemsetD32':(D,U,S),
    'cuEventCreate':(P,U),
    'cuEventRecord':(V,V),
    'cuEventSynchronize':(V,),
    'cuEventDestroy':(V,),
    'cuEventElapsedTime':(c.POINTER(c.c_float),V,V),
    'cuGetErrorName':(I,c.POINTER(c.c_char_p)),
    'cuGetErrorString':(I,c.POINTER(c.c_char_p)),
    # Keep input string pointers opaque: a deny callback must not copy pointees.
    'cuModuleGetGlobal':(DP,SP,V,V),
    'cuModuleGetFunction':(P,V,V),
    'cuFuncGetParamInfo':(V,S,SP,SP),
    'cuModuleUnload':(V,),
}
for name in ('cuDevicePrimaryCtxSetFlags','cuDevicePrimaryCtxReset','cuDevicePrimaryCtxRelease',
             'cuCtxCreate','cuCtxDestroy','cuCtxPushCurrent','cuCtxPopCurrent','cuMemAlloc','cuMemFree',
             'cuMemGetAddressRange','cuMemcpyHtoD','cuMemcpyDtoH','cuMemcpyDtoD','cuMemsetD8','cuMemsetD16',
             'cuMemsetD32','cuEventDestroy','cuModuleGetGlobal'):
    GUARDED[name+'_v2']=GUARDED[name]
