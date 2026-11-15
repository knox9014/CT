"""Forward75/76/15/40 and one real unsupported query, then block forwarding."""
import ctypes as c
from runtime_metadata_observer import MetadataObserver
from runtime_scheduling_check import PREFIX,boundary_attribute
from scheduling_pointer_guards import GUARDED


class SchedulingObserver(MetadataObserver):
    def _select_pointer(self,symbol,pointer,requested=None):
        if pointer and symbol not in self.bindings:
            name=symbol.decode('ascii',errors='replace');arguments=GUARDED.get(name)
            if arguments is None:
                self._failure('unwrapped_provider_symbol');return None
            signature=c.WINFUNCTYPE(c.c_int,*arguments)
            def deny(*args):
                event=dict(kind='guard',symbol=name,result=801,output_cleared=False)
                self.guard_hits.append(event);self.trace.append(event);return 801
            wrapper=self._callback('scheduling_deny_'+name,signature,deny)
            self.bindings[symbol]=(wrapper,signature(pointer));self.callbacks.append(wrapper)
            self.trace.append(dict(kind='scheduling_guard_binding',symbol=name))
        return super()._select_pointer(symbol,pointer,requested)

    def _scheduling_ready(self,output,attribute,ordinal):
        index=self.metadata_step-2
        valid=(0<=index<len(PREFIX) and attribute==PREFIX[index][0]) or (index==len(PREFIX) and boundary_attribute(attribute))
        if not valid:
            self._failure('scheduling_attribute_order');return False
        return self._metadata_ready(output,ordinal,2+index)

    def _additional_bindings(self):
        bindings=super()._additional_bindings();signature=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_int),c.c_int,c.c_int)
        actual=signature(('cuDeviceGetAttribute',self.provider))
        def attribute(output,requested,ordinal):
            if not self._scheduling_ready(output,requested,ordinal):return 999
            index=self.metadata_step-2;boundary=index==len(PREFIX)
            expected_result,expected_value=(801,0) if boundary else PREFIX[index][1:]
            result=actual(output,requested,ordinal);value=output[0]
            self.trace.append(dict(kind='scheduling_attribute_boundary' if boundary else 'scheduling_attribute_call',
                                   symbol='cuDeviceGetAttribute',attribute=requested,ordinal=ordinal,result=result,value=value))
            if result!=expected_result or value!=expected_value:self._failure('scheduling_attribute_result');return 999
            self.metadata_step+=1
            if boundary:self.boundary_seen=True
            return result
        bindings[b'cuDeviceGetAttribute']=(self._callback('scheduling_attribute',signature,attribute,clear_output=0),actual)
        return bindings
