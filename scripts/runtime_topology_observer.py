"""Forward75/76/15/40 and one real unsupported query, then block forwarding."""
import ctypes as c
from runtime_metadata_observer import MetadataObserver
from runtime_topology_check import prefix,boundary_attribute
from scheduling_pointer_guards import GUARDED


class TopologyObserver(MetadataObserver):
    def __init__(self,*args,topology_count,**kwargs):
        prefix(topology_count);self.topology_count=topology_count
        super().__init__(*args,**kwargs)

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
        steps=prefix(self.topology_count);index=self.metadata_step-2
        valid=(0<=index<len(steps) and attribute==steps[index][0]) or (index==len(steps) and boundary_attribute(attribute))
        if not valid:
            self._failure('scheduling_attribute_order');return False
        return self._metadata_ready(output,ordinal,2+index)

    def _additional_bindings(self):
        bindings=super()._additional_bindings();signature=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_int),c.c_int,c.c_int)
        actual=signature(('cuDeviceGetAttribute',self.provider))
        def attribute(output,requested,ordinal):
            if not self._scheduling_ready(output,requested,ordinal):return 999
            steps=prefix(self.topology_count);index=self.metadata_step-2;boundary=index==len(steps)
            expected_result,expected_value=(801,0) if boundary else steps[index][1:]
            result=actual(output,requested,ordinal);value=output[0]
            self.trace.append(dict(kind='scheduling_attribute_boundary' if boundary else 'scheduling_attribute_call',
                                   symbol='cuDeviceGetAttribute',attribute=requested,ordinal=ordinal,result=result,value=value))
            if result!=expected_result or value!=expected_value:self._failure('scheduling_attribute_result');return 999
            self.metadata_step+=1
            if boundary:self.boundary_seen=True
            return result
        bindings[b'cuDeviceGetAttribute']=(self._callback('scheduling_attribute',signature,attribute,clear_output=0),actual)
        return bindings
