"""Require the current unsupported array to survive compilation and registration."""
import re
def validate_negative(ptx,stub):
    array=re.search(r'\.global\s+\.align\s+8\s+\.b8\s+ct_used_global\s*\[16\]',ptx)
    load='ld.volatile.global.u8' in ptx
    registration=re.search(r'__cudaRegisterVariable\([^;]*ct_used_global[^;]*,\s*0,\s*16Ui64,\s*0,\s*0\)',stub)
    return [] if array and load and registration else ['unsupported array compiler metadata']
