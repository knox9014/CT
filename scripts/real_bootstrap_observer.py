"""Real CT diagnostic only: guarded forwarding plus explicit version intervention."""
import ctypes as c
from cupy_bootstrap_observer import Observer

class GuardedObserver(Observer):
    def __init__(self,provider,*,sample=None,contract_mode=False):
        if sample is not None and (type(sample) is not int or sample not in (12000,12090)):raise ValueError('fixed reviewed samples only')
        if type(contract_mode) is not bool:raise ValueError('explicit contract mode')
        self.sample=sample;self.guard_hits=[];self.contract_mode=contract_mode;self.blocked_callbacks=[]
        super().__init__(provider)

    def _forwarding_blocked(self):
        return bool(self.callback_failures) or (bool(self.guard_hits) and not self.contract_mode)

    def _record_blocked(self,label):
        if label not in self.blocked_callbacks:
            self.blocked_callbacks.append(label)
            self.trace.append(dict(kind='blocked_after_guard_or_failure',callback=label))

    def _present_version(self,result,output):
        if self.sample is None or not output:return result
        original=output[0]
        if result!=801 or original!=0:
            self._failure('version_intervention_precondition');return result
        output[0]=self.sample
        self.trace.append(dict(kind='intervention',symbol='cuDriverGetVersion',original_result=result,
                               original_value=original,presented_result=0,presented_value=self.sample))
        return 0

    def _select_pointer(self,symbol,pointer,requested=None):
        if symbol==b'<ordinal>' and pointer:
            self._failure('unreviewed_ordinal_lookup');return None
        return super()._select_pointer(symbol,pointer,requested)

    def _additional_bindings(self):
        count_type=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_int))
        module_type=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_void_p),c.c_void_p)
        launch_type=c.WINFUNCTYPE(c.c_int,c.c_void_p,*([c.c_uint]*7),c.c_void_p,c.POINTER(c.c_void_p),c.POINTER(c.c_void_p))
        real_count=count_type(('cuDeviceGetCount',self.provider))
        real_module=module_type(('cuModuleLoadData',self.provider))
        real_launch=launch_type(('cuLaunchKernel',self.provider))
        def count(output):
            result=real_count(output)
            self.trace.append(dict(kind='call',symbol='cuDeviceGetCount',result=result,value=output[0] if output else None))
            return result
        def module(output,image):
            if output:output[0]=None
            event=dict(kind='guard',symbol='cuModuleLoadData',result=801,output_cleared=bool(output))
            self.guard_hits.append(event);self.trace.append(event);return 801
        def launch(function,gx,gy,gz,bx,by,bz,shared,stream,arguments,extra):
            event=dict(kind='guard',symbol='cuLaunchKernel',result=801,output_cleared=False)
            self.guard_hits.append(event);self.trace.append(event);return 801
        return {b'cuDeviceGetCount':(self._callback('count',count_type,count,clear_output=0),real_count),
                b'cuModuleLoadData':(self._callback('module_guard',module_type,module),real_module),
                b'cuLaunchKernel':(self._callback('launch_guard',launch_type,launch),real_launch)}
