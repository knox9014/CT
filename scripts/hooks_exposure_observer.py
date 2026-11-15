"""Both typed deny layouts; expected private context entry is not support."""
import ctypes as c
import struct
from table_exposure_observer import ExposureObserver,FixtureOwner,NEXT
from export_reject_observer import ExportRejectObserver


def validate_hooks_layout(base,size,address,words):
    if (any(type(v) is not int for v in (base,size,address)) or base<=65535 or size<56 or address%8
            or not base<=address or address+56>base+size or type(words) is not list or len(words)!=7
            or any(type(w) is not int for w in words)):raise ValueError('hooks bounds/type')
    if words[0]!=56 or any(words[i]!=0 for i in (1,3,4,5)):raise ValueError('hooks metadata/holes')
    if any(not base<=words[i]<base+size for i in (2,6)):raise ValueError('hooks callback outside fixture')


class HooksOwner(FixtureOwner):
    def __init__(self,manifest,path):
        super().__init__(manifest,path)
        output=c.c_void_p()
        if self.library.ctTableGet(1,c.byref(output))!=0 or not output.value:raise ValueError('hooks table missing')
        raw=self.path.read_bytes();pe=struct.unpack_from('<I',raw,60)[0];size=struct.unpack_from('<I',raw,pe+24+56)[0]
        base=self.library._handle;self.hooks_address=output.value
        if self.hooks_address%8 or not base<=self.hooks_address or self.hooks_address+56>base+size:raise ValueError('hooks outside image')
        validate_hooks_layout(base,size,self.hooks_address,list((c.c_uint64*7).from_address(self.hooks_address)))


class HooksObserver(ExposureObserver):
    def _forwarding_blocked(self):
        state=self.owner.state()
        if state==dict(mask=0,stopped=0,reserved=0):return ExportRejectObserver._forwarding_blocked(self)
        if state!=dict(mask=2,stopped=1,reserved=0) or self.phase!=3:self._failure('unexpected_private_callback')
        return True

    def _additional_bindings(self):
        bindings=super()._additional_bindings()
        signature=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_int),c.c_int)
        actual=signature(('cuDeviceGet',self.provider))
        def get(output,ordinal):
            result=actual(output,ordinal)
            self.trace.append(dict(kind='device_get_call',symbol='cuDeviceGet',ordinal=ordinal,result=result,value=output[0] if output else None))
            return result
        bindings[b'cuDeviceGet']=(self._callback('device_get',signature,get,clear_output=0),actual)
        return bindings

    def reject_export(self,output,uuid):
        if self.phase!=2:return super().reject_export(output,uuid)
        if output:output[0]=None
        if not output or not uuid:
            self._failure('null_hooks_query');return 1
        if c.string_at(uuid,16).hex()!=NEXT:
            self._failure('unreviewed_hooks_query');return 999
        if self._forwarding_blocked():return 999
        output[0]=self.owner.hooks_address;self.phase=3
        self.trace.append(dict(kind='hooks_exposure',symbol='cuGetExportTable',uuid=NEXT,result=0,byte_size=56,fixture_kind='hooks_deny_only'))
        return 0
