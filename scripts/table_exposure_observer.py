"""CUDART-only diagnostic pointer presentation, never a private table service."""
import ctypes as c
import json
from pathlib import Path
import struct
from export_reject_observer import ExportRejectObserver,IDS
from run_typed_tables import ROOT,audit
from run_cupy_bootstrap import digest
from runtime_bootstrap_worker import require_loaded

NEXT='a094798c2e742e7493f20800200c0a66'


def validate_layout(base,size,address,words):
    if (any(type(v) is not int for v in (base,size,address)) or base<=65535 or size<104
            or address%8 or not base<=address or address+104>base+size
            or type(words) is not list or len(words)!=13 or any(type(w) is not int for w in words)):
        raise ValueError('table image bounds/type')
    if words[0]!=104 or any(words[i]!=0 for i in (3,5,9,10,11)):raise ValueError('table metadata/holes')
    if any(not base<=words[i]<base+size for i in (1,2,4,6,7,8,12)):raise ValueError('callback outside fixture image')


class State(c.Structure):
    _fields_=[('mask',c.c_uint64),('stopped',c.c_uint32),('reserved',c.c_uint32)]


class FixtureOwner:
    def __init__(self,manifest,path):
        manifest=manifest.resolve();folder=manifest.parent
        if not folder.is_relative_to((ROOT/'.cache/typed-table-runs').resolve()) or manifest.name!='capture.json':raise ValueError('local reviewed fixture required')
        record=json.loads(manifest.read_bytes());audit(folder,record)
        if digest(path)!=record['artifacts']['tables.dll']:raise ValueError('copied fixture differs')
        self.kernel=c.WinDLL('kernel32',use_last_error=True)
        self.kernel.GetModuleHandleW.argtypes=[c.c_wchar_p];self.kernel.GetModuleHandleW.restype=c.c_void_p
        self.kernel.FreeLibrary.argtypes=[c.c_void_p];self.kernel.FreeLibrary.restype=c.c_int
        self.path=path.resolve();self.closed=False;self.prefix_state=None
        if self.kernel.GetModuleHandleW(str(self.path)):raise ValueError('fixture already loaded')
        self.library=c.WinDLL(str(self.path));self.sha=require_loaded(self.library,self.path)
        self.query=self.library.ctTableState;self.query.argtypes=[c.POINTER(State)];self.query.restype=c.c_int
        self.initial=self.state()
        if self.initial!=dict(mask=0,stopped=0,reserved=0):raise ValueError('fixture already latched')
        get=self.library.ctTableGet;get.argtypes=[c.c_uint32,c.POINTER(c.c_void_p)];get.restype=c.c_int
        output=c.c_void_p()
        if get(0,c.byref(output))!=0 or not output.value:raise ValueError('fixture table missing')
        raw=self.path.read_bytes();pe=struct.unpack_from('<I',raw,60)[0];size=struct.unpack_from('<I',raw,pe+24+56)[0]
        self.address=output.value;base=self.library._handle
        # Validate the full read range before touching table storage.
        if self.address%8 or not base<=self.address or self.address+104>base+size:raise ValueError('table outside image')
        validate_layout(base,size,self.address,list((c.c_uint64*13).from_address(self.address)))

    def state(self):
        if self.closed:raise ValueError('fixture state after unload')
        value=State()
        if self.query(c.byref(value))!=0:raise ValueError('fixture state failed')
        return dict(mask=value.mask,stopped=value.stopped,reserved=value.reserved)

    def close(self):
        if self.closed:raise ValueError('fixture already unloaded')
        # No fixture calls/memory reads are permitted after this point.
        freed=bool(self.kernel.FreeLibrary(self.library._handle));self.closed=True
        return dict(free_succeeded=freed,module_absent=not bool(self.kernel.GetModuleHandleW(str(self.path))))


class ExposureObserver(ExportRejectObserver):
    def __init__(self,provider,*,owner,**kwargs):
        self.owner=owner;self.phase=0
        super().__init__(provider,**kwargs)

    def _forwarding_blocked(self):
        if self.owner.state()!=dict(mask=0,stopped=0,reserved=0):self._failure('private_table_callback')
        return super()._forwarding_blocked()

    def reject_export(self,output,uuid):
        if output:output[0]=None
        if not output or not uuid:
            self._failure('null_table_query');return 1
        identifier=c.string_at(uuid,16).hex()
        if self.phase>=3 or identifier!=(IDS[0],IDS[1],NEXT)[self.phase]:
            self._failure('unreviewed_table_query_order');return 999
        if self._forwarding_blocked():return 999
        if self.phase==1:
            calls=[r for r in self.trace if r.get('kind')=='call']
            expected=[dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0),dict(kind='call',symbol='cuInit',flags=0,result=0)]
            if calls!=expected or self.sample not in (12000,12090):
                self._failure('table_before_actual_init');return 999
            output[0]=self.owner.address
            event=dict(kind='table_exposure',symbol='cuGetExportTable',uuid=identifier,result=0,byte_size=104,fixture_kind='cudart_deny_only')
        else:
            event=dict(kind='export_rejection' if self.phase==0 else 'known_next_rejection',symbol='cuGetExportTable',uuid=identifier,result=801,output_cleared=True)
        self.phase+=1;self.trace.append(event);return event['result']

    def restore(self):
        if not self.restored:
            try:self.owner.prefix_state=self.owner.state()
            except Exception:self._failure('private_prefix_state_failed')
        return super().restore()
