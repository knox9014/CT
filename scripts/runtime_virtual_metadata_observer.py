"""Actual explicit-target 75/76 values, stopping on the actual attribute15 refusal."""
import ctypes as c
from runtime_metadata_observer import MetadataObserver
from runtime_virtual_metadata_check import ATTRIBUTES


class VirtualMetadataObserver(MetadataObserver):
    def _virtual_ready(self,output,attribute,ordinal):
        index=self.metadata_step-2
        if not 0<=index<len(ATTRIBUTES) or attribute!=ATTRIBUTES[index][0]:
            self._failure('virtual_attribute_order');return False
        return self._metadata_ready(output,ordinal,2+index)

    def _additional_bindings(self):
        bindings=super()._additional_bindings();signature=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_int),c.c_int,c.c_int)
        actual=signature(('cuDeviceGetAttribute',self.provider))
        def attribute(output,requested,ordinal):
            if not self._virtual_ready(output,requested,ordinal):return 999
            _,expected_result,expected_value=ATTRIBUTES[self.metadata_step-2]
            result=actual(output,requested,ordinal);value=output[0]
            self.trace.append(dict(kind='virtual_attribute_boundary' if requested==15 else 'virtual_attribute_call',
                                   symbol='cuDeviceGetAttribute',attribute=requested,ordinal=ordinal,result=result,value=value))
            if result!=expected_result or value!=expected_value:self._failure('virtual_attribute_result');return 999
            self.metadata_step+=1
            if requested==15:self.boundary_seen=True
            return result
        bindings[b'cuDeviceGetAttribute']=(self._callback('virtual_attribute',signature,attribute,clear_output=0),actual)
        return bindings
