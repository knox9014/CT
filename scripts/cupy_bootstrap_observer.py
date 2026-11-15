"""Diagnostic-only import-slot observation inside one Windows CuPy child.

Returned bootstrap function addresses are wrapped; original result/output values
are forwarded. This is not the nominal run and is not a general tracing engine.
"""
import ctypes as c
from pathlib import Path
from cupy_bootstrap_check import import_slots


class Observer:
    def __init__(self,provider):
        self.provider=provider
        self.trace=[];self.saved=[];self.callbacks=[];self.restored=False;self.callback_failures=[]
        self.kernel=c.WinDLL('kernel32',use_last_error=True)
        self.kernel.GetModuleHandleW.argtypes=[c.c_wchar_p]
        self.kernel.GetModuleHandleW.restype=c.c_void_p
        self.kernel.GetProcAddress.argtypes=[c.c_void_p,c.c_void_p]
        self.kernel.GetProcAddress.restype=c.c_void_p
        self.kernel.VirtualProtect.argtypes=[c.c_void_p,c.c_size_t,c.c_uint32,c.POINTER(c.c_uint32)]
        self.kernel.VirtualProtect.restype=c.c_int
        self.real_lookup=self.kernel.GetProcAddress
        self._wrappers()

    def _failure(self,label):
        if label not in self.callback_failures:
            self.callback_failures.append(label)
            self.trace.append(dict(kind='callback_failure',callback=label))

    def _callback(self,label,signature,function,*,failure=999,clear_output=None):
        def failed(args):
            if clear_output is not None:
                try:
                    output=args[clear_output]
                    if output:output[0]=None if label.startswith('resolver') else 0
                except Exception:pass
            return failure
        def invoke(*args):
            try:
                if self._forwarding_blocked():
                    self._record_blocked(label)
                    return failed(args)
                return function(*args)
            except Exception:
                self._failure(label)
                return failed(args)
        return signature(invoke)

    def _forwarding_blocked(self):return bool(self.callback_failures)

    def _record_blocked(self,label):pass

    def _present_version(self,result,output):return result

    def _additional_bindings(self):return {}

    def _select_pointer(self,symbol,pointer,requested=None):
        if not pointer:return pointer
        key=b'cuGetProcAddress_v2' if symbol==b'cuGetProcAddress' and requested is not None and requested>=12000 else symbol
        binding=self.bindings.get(key)
        if binding is None:return pointer
        wrapper,actual=binding
        if pointer!=c.cast(actual,c.c_void_p).value:
            self._failure('binding_mismatch');return None
        return c.cast(wrapper,c.c_void_p).value

    def _wrappers(self):
        resolver2=c.WINFUNCTYPE(c.c_int,c.c_char_p,c.POINTER(c.c_void_p),c.c_int,c.c_uint64,c.POINTER(c.c_int))
        resolver1=c.WINFUNCTYPE(c.c_int,c.c_char_p,c.POINTER(c.c_void_p),c.c_int,c.c_uint64)
        init_type=c.WINFUNCTYPE(c.c_int,c.c_uint)
        version_type=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_int))
        real2=resolver2(('cuGetProcAddress_v2',self.provider))
        real1=resolver1(('cuGetProcAddress',self.provider))
        real_init=init_type(('cuInit',self.provider))
        real_version=version_type(('cuDriverGetVersion',self.provider))
        def name(symbol):return symbol.decode('ascii') if symbol is not None else '<null>'
        def init(flags):
            result=real_init(flags)
            self.trace.append(dict(kind='call',symbol='cuInit',flags=flags,result=result))
            return result
        init=self._callback('init',init_type,init)
        def version(output):
            result=real_version(output)
            self.trace.append(dict(kind='call',symbol='cuDriverGetVersion',result=result,value=output[0] if output else None))
            return self._present_version(result,output)
        version=self._callback('version',version_type,version,clear_output=0)
        def wrap(symbol,output,requested,result):
            if result!=0 or not output or not output[0]:return
            output[0]=self._select_pointer(symbol,output[0],requested)
        def resolve1(symbol,output,requested,flags):
            result=real1(symbol,output,requested,flags)
            self.trace.append(dict(kind='resolver_v1',symbol=name(symbol),version=requested,flags=flags,
                                   result=result,found=bool(output[0]) if output else None))
            wrap(symbol,output,requested,result)
            if self.callback_failures:return 999
            return result
        resolve1=self._callback('resolver_v1',resolver1,resolve1,clear_output=1)
        def resolve2(symbol,output,requested,flags,status):
            result=real2(symbol,output,requested,flags,status)
            self.trace.append(dict(kind='resolver_v2',symbol=name(symbol),version=requested,flags=flags,
                                   result=result,status=status[0] if status else None,found=bool(output[0]) if output else None))
            wrap(symbol,output,requested,result)
            if self.callback_failures:
                if status:status[0]=1
                return 999
            return result
        resolve2=self._callback('resolver_v2',resolver2,resolve2,clear_output=1)
        self.bindings={b'cuGetProcAddress_v2':(resolve2,real2),b'cuGetProcAddress':(resolve1,real1),
                       b'cuInit':(init,real_init),b'cuDriverGetVersion':(version,real_version)}
        self.bindings.update(self._additional_bindings())
        def make_lookup(original):
            def lookup(handle,symbol):
                result=original(handle,symbol)
                if handle!=self.provider._handle:return result
                text=c.string_at(symbol) if symbol and symbol>65535 else b'<ordinal>'
                self.trace.append(dict(kind='lookup',symbol=text.decode('ascii'),found=bool(result)))
                return self._select_pointer(text,result)
            return self._callback('lookup',c.WINFUNCTYPE(c.c_void_p,c.c_void_p,c.c_void_p),lookup,failure=None)
        self.make_lookup=make_lookup
        self.callbacks=[binding[0] for binding in self.bindings.values()]

    def _write(self,slot,value):
        old=c.c_uint32()
        if not self.kernel.VirtualProtect(slot,8,4,c.byref(old)):raise OSError('IAT protection change failed')
        try:c.c_uint64.from_address(slot).value=value
        finally:
            if not self.kernel.VirtualProtect(slot,8,old.value,c.byref(c.c_uint32())):
                raise OSError('IAT protection restore failed')

    def install(self,modules,*,native_probe=False):
        try:
            if type(native_probe) is not bool:raise ValueError('explicit native probe mode required')
            for module in modules:
                path=Path(module.__file__)
                suffix='.dll' if native_probe else '.pyd'
                if path.suffix.lower()!=suffix:raise ValueError('observer requires the selected native module kind')
                _,slots=import_slots(path.read_bytes())
                base=self.kernel.GetModuleHandleW(str(path))
                if not base:raise OSError('CuPy module not loaded')
                lookup_addresses={c.cast(self.real_lookup,c.c_void_p).value}
                if native_probe:
                    self.api_set=c.WinDLL('api-ms-win-core-libraryloader-l1-2-0.dll',use_last_error=True)
                    lookup_addresses.add(c.cast(self.api_set.GetProcAddress,c.c_void_p).value)
                for rva in slots:
                    slot=base+rva
                    previous=c.c_uint64.from_address(slot).value
                    if previous not in lookup_addresses:
                        raise ValueError('unexpected or already instrumented loader slot')
                    if any(s==slot for s,_ in self.saved):raise ValueError('duplicate module slot')
                    self.saved.append((slot,previous))
                    original=c.WINFUNCTYPE(c.c_void_p,c.c_void_p,c.c_void_p)(previous)
                    lookup=self.make_lookup(original);self.callbacks.append(lookup)
                    self._write(slot,c.cast(lookup,c.c_void_p).value)
            if not self.saved:raise ValueError('no observable CuPy import slot')
        except BaseException:
            self.restore()
            raise

    def restore(self):
        failures=[]
        for slot,previous in reversed(self.saved):
            try:
                self._write(slot,previous)
                if c.c_uint64.from_address(slot).value!=previous:raise OSError('IAT restoration mismatch')
            except OSError:failures.append(slot)
        self.restored=not failures
        if failures:raise OSError('IAT restoration failed')
        if self.callback_failures:raise ValueError('native callback failure; capture invalid')
