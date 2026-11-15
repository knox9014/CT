"""Explicit v2-only diagnostic surface presentation; never a private table."""
import ctypes as c
from real_bootstrap_observer import GuardedObserver

IDS=('f8cff95121468b4eb9e2fb469e7c0dd9','6bd5fb6c5bf4e74a8987d93912fd9df9')


class ExportRejectObserver(GuardedObserver):
    def reject_export(self,output,uuid):
        if output:output[0]=None
        if not output or not uuid:
            self.trace.append(dict(kind='export_rejection',symbol='cuGetExportTable',uuid=None,result=1,output_cleared=bool(output)))
            return 1
        identifier=c.string_at(uuid,16).hex()
        if identifier not in IDS:
            self._failure('unreviewed_export_identifier');return 999
        self.trace.append(dict(kind='export_rejection',symbol='cuGetExportTable',uuid=identifier,result=801,output_cleared=True))
        return 801

    def present_export(self,symbol,output,requested,flags,status,result):
        if symbol!=b'cuGetExportTable':return result
        original_status=status[0] if status else None
        if (type(result) is not int or result!=0 or not output or output[0] or requested!=3000
                or flags!=0 or original_status not in (None,1)):
            if output:output[0]=None
            if status:status[0]=1
            self._failure('export_surface_precondition');return 999
        output[0]=c.cast(self.export_callback,c.c_void_p).value
        if status:status[0]=0
        self.trace.append(dict(kind='export_surface_intervention',symbol='cuGetExportTable',version=requested,flags=flags,
                               original_result=result,original_found=False,original_status=original_status,
                               presented_result=0,presented_found=True,presented_status=0 if status else None))
        return 0

    def _wrappers(self):
        super()._wrappers()
        signature=c.WINFUNCTYPE(c.c_int,c.POINTER(c.c_void_p),c.c_void_p)
        self.export_callback=self._callback('export_reject',signature,self.reject_export,clear_output=0)
        inner,actual=self.bindings[b'cuGetProcAddress_v2']
        resolver=c.WINFUNCTYPE(c.c_int,c.c_char_p,c.POINTER(c.c_void_p),c.c_int,c.c_uint64,c.POINTER(c.c_int))
        def resolve(symbol,output,requested,flags,status):
            result=inner(symbol,output,requested,flags,status)
            if self.callback_failures:return 999
            return self.present_export(symbol,output,requested,flags,status,result)
        outer=self._callback('resolver_export',resolver,resolve,clear_output=1)
        self.bindings[b'cuGetProcAddress_v2']=(outer,actual)
        self.callbacks.extend((inner,outer,self.export_callback))
