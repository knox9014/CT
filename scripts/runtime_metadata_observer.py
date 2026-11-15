"""Forward actual name/total; observe and stop on actual strict attr75 refusal."""
import ctypes as c
from primary_runtime_observer import PrimaryObserver


class MetadataObserver(PrimaryObserver):
    def __init__(self,*args,**kwargs):
        self.metadata_step=0
        super().__init__(*args,**kwargs)

    def _metadata_ready(self,output,ordinal,step):
        if not output or ordinal!=0 or self.phase!=3 or self.metadata_step!=step or self.owner.native_state()!=dict(calls=1,result=0,nonnull=1):
            self._failure('metadata_order_or_arguments');return False
        return True

    def _additional_bindings(self):
        bindings=super()._additional_bindings()
        name_type=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_char),c.c_int,c.c_int)
        total_type=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_size_t),c.c_int)
        attr_type=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_int),c.c_int,c.c_int)
        real_name=name_type(('cuDeviceGetName',self.provider));real_total=total_type(('cuDeviceTotalMem_v2',self.provider))
        real_attr=attr_type(('cuDeviceGetAttribute',self.provider))
        def name(output,length,ordinal):
            if length!=256 or not self._metadata_ready(output,ordinal,0):self._failure('name_metadata_arguments');return 999
            result=real_name(output,length,ordinal);raw=c.string_at(output,256)
            if result!=0 or b'\0' not in raw:self._failure('name_metadata_result');return 999
            text=raw.split(b'\0',1)[0].decode('utf-8');self.metadata_step=1
            self.trace.append(dict(kind='device_name_call',symbol='cuDeviceGetName',length=length,ordinal=ordinal,result=result,value=text));return result
        def total(output,ordinal):
            if not self._metadata_ready(output,ordinal,1):return 999
            result=real_total(output,ordinal);value=output[0]
            self.trace.append(dict(kind='device_total_call',symbol='cuDeviceTotalMem',ordinal=ordinal,result=result,total_bytes=value))
            if result!=0 or value<=0:self._failure('total_metadata_result');return 999
            self.metadata_step=2;return result
        def attr(output,attribute,ordinal):
            if attribute!=75 or not self._metadata_ready(output,ordinal,2):self._failure('attribute_metadata_arguments');return 999
            result=real_attr(output,attribute,ordinal);value=output[0]
            self.trace.append(dict(kind='strict_attribute_boundary',symbol='cuDeviceGetAttribute',attribute=attribute,ordinal=ordinal,result=result,value=value))
            if result!=801 or value!=0:self._failure('strict_attribute_result');return 999
            self.metadata_step=3;self.boundary_seen=True;return result
        total_callback=self._callback('total_metadata',total_type,total,clear_output=0)
        bindings[b'cuDeviceGetName']=(self._callback('name_metadata',name_type,name),real_name)
        bindings[b'cuDeviceTotalMem']=(total_callback,real_total);bindings[b'cuDeviceTotalMem_v2']=(total_callback,real_total)
        bindings[b'cuDeviceGetAttribute']=(self._callback('attribute_metadata',attr_type,attr,clear_output=0),real_attr)
        return bindings
