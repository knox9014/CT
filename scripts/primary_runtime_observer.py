"""Diagnostic same-provider owner and next-call stop; provider is not unloaded."""
import ctypes as c
import struct
from hooks_exposure_observer import HooksObserver,validate_hooks_layout
from table_exposure_observer import State,validate_layout
from export_reject_observer import ExportRejectObserver


class NativeState(c.Structure):
    _fields_=[('calls',c.c_uint64),('result',c.c_int32),('nonnull',c.c_uint32)]


class PrimaryOwner:
    def __init__(self,provider,path):
        self.library=provider;self.prefix_state=None;self.native_prefix=None
        self.query=provider.ctTableState;self.query.argtypes=[c.POINTER(State)];self.query.restype=c.c_int
        self.native_query=provider.ctPrimaryState;self.native_query.argtypes=[c.POINTER(NativeState)];self.native_query.restype=c.c_int
        self.initial=self.state();self.native_initial=self.native_state()
        if self.initial!=dict(mask=0,stopped=0,reserved=0) or self.native_initial!=dict(calls=0,result=0,nonnull=0):raise ValueError('provider state not fresh')
        raw=path.read_bytes();pe=struct.unpack_from('<I',raw,60)[0];size=struct.unpack_from('<I',raw,pe+24+56)[0];base=provider._handle
        get=provider.ctPrimaryTableGet;get.argtypes=[c.POINTER(c.c_void_p)];get.restype=c.c_int
        output=c.c_void_p()
        if get(c.byref(output))!=0 or not output.value:raise ValueError('native table missing')
        self.address=output.value
        if self.address%8 or not base<=self.address or self.address+104>base+size:raise ValueError('native table bounds')
        validate_layout(base,size,self.address,list((c.c_uint64*13).from_address(self.address)))
        hooks=provider.ctTableGet;hooks.argtypes=[c.c_uint32,c.POINTER(c.c_void_p)];hooks.restype=c.c_int
        if hooks(1,c.byref(output))!=0 or not output.value:raise ValueError('hooks missing')
        self.hooks_address=output.value
        if self.hooks_address%8 or not base<=self.hooks_address or self.hooks_address+56>base+size:raise ValueError('hooks bounds')
        validate_hooks_layout(base,size,self.hooks_address,list((c.c_uint64*7).from_address(self.hooks_address)))

    def state(self):
        value=State()
        if self.query(c.byref(value))!=0:raise ValueError('deny state failed')
        return dict(mask=value.mask,stopped=value.stopped,reserved=value.reserved)

    def native_state(self):
        value=NativeState()
        if self.native_query(c.byref(value))!=0:raise ValueError('native state failed')
        return dict(calls=value.calls,result=value.result,nonnull=value.nonnull)


class PrimaryObserver(HooksObserver):
    def __init__(self,*args,**kwargs):
        self.boundary_seen=False;self.state_failures=[];self.current_lookup=None;self.foreign_lookups=[]
        super().__init__(*args,**kwargs)
        factory=self.make_lookup
        self.make_lookup=lambda original:self.scoped_lookup(factory,original)

    def scoped_lookup(self,factory,original):
        delegate=factory(original)
        def probe(handle,symbol):
            try:
                text=c.string_at(symbol).decode('ascii',errors='replace') if symbol and symbol>65535 else '<ordinal>'
                if handle!=self.provider._handle:
                    # Windows loader queries are outside the CUDA forwarding gate.
                    self.foreign_lookups.append(dict(symbol=text,phase=self.phase,native=self.owner.native_state()))
                    return original(handle,symbol)
                self.current_lookup=dict(same_provider=True,symbol=text)
                return delegate(handle,symbol)
            except Exception:
                self._failure('loader_scope_probe');return None
            finally:self.current_lookup=None
        callback=c.WINFUNCTYPE(c.c_void_p,c.c_void_p,c.c_void_p)(probe)
        self.callbacks.extend((delegate,callback));return callback

    def _forwarding_blocked(self):
        if self.owner.state()!=dict(mask=0,stopped=0,reserved=0):self._failure('private_denial')
        native=self.owner.native_state()
        if native not in (dict(calls=0,result=0,nonnull=0),dict(calls=1,result=0,nonnull=1)):
            self.state_failures.append(dict(native=native,phase=self.phase,lookup=self.current_lookup))
            self._failure('unexpected_context_state')
        if native['calls'] and self.phase!=3:self._failure('context_before_tables')
        return self.boundary_seen or ExportRejectObserver._forwarding_blocked(self)

    def _additional_bindings(self):
        bindings=super()._additional_bindings();signature=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_char),c.c_int,c.c_int)
        actual=signature(('cuDeviceGetName',self.provider))
        def name(output,length,ordinal):
            if not output or length!=256 or ordinal!=0 or self.phase!=3 or self.owner.native_state()!=dict(calls=1,result=0,nonnull=1):
                self._failure('unreviewed_name_boundary');return 999
            output[0]=b'\0';self.boundary_seen=True
            self.trace.append(dict(kind='next_public_boundary',symbol='cuDeviceGetName',length=length,ordinal=ordinal,result=801,output_cleared=True))
            return 801
        bindings[b'cuDeviceGetName']=(self._callback('name_boundary',signature,name),actual)
        return bindings

    def reject_export(self,output,uuid):
        result=super().reject_export(output,uuid)
        if self.trace and self.trace[-1].get('kind')=='table_exposure':self.trace[-1]['fixture_kind']='cudart_native_context_only'
        return result

    def restore(self):
        if not self.restored:
            try:self.owner.native_prefix=self.owner.native_state()
            except Exception:self._failure('native_prefix_state_failed')
        return super().restore()
