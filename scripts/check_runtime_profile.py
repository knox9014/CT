"""Check the closed Runtime ABI contract; this is not execution evidence."""
import json
from pathlib import Path, PurePosixPath
import re

REPO = Path(__file__).resolve().parents[1]
PROFILE = 'docs/compatibility/runtime-profile-v1.json'
BASE_SIGNATURES = {
    'cudaGetDeviceCount':'i32(out_i32)', 'cudaGetDevice':'i32(out_i32)',
    'cudaSetDevice':'i32(i32)', 'cudaDeviceSynchronize':'i32()',
    'cudaMalloc':'i32(out_ptr,size)', 'cudaFree':'i32(ptr)',
    'cudaMemcpy':'i32(ptr,const_ptr,size,i32)', 'cudaMemset':'i32(ptr,i32,size)',
    'cudaGetLastError':'i32()', 'cudaPeekAtLastError':'i32()',
    'cudaGetErrorName':'const_char_ptr(i32)', 'cudaGetErrorString':'const_char_ptr(i32)',
    'cudaDriverGetVersion':'i32(out_i32)', 'cudaRuntimeGetVersion':'i32(out_i32)',
}
KERNEL_SIGNATURES = {**BASE_SIGNATURES,
    '__cudaRegisterFatBinary':'ptr_ptr(ptr)',
    '__cudaRegisterFatBinaryEnd':'void(ptr_ptr)',
    '__cudaUnregisterFatBinary':'void(ptr_ptr)',
    '__cudaRegisterFunction':'void(ptr_ptr,const_char_ptr,char_ptr,const_char_ptr,i32,uint3_ptr,uint3_ptr,dim3_ptr,dim3_ptr,i32_ptr)',
    '__cudaPushCallConfiguration':'u32(dim3,dim3,size,stream)',
    '__cudaPopCallConfiguration':'i32(dim3_ptr,dim3_ptr,size_ptr,ptr)',
    'cudaLaunchKernel':'i32(const_ptr,dim3,dim3,ptr_ptr,size,stream)',
}
REGISTRATION_SIGNATURES = {**KERNEL_SIGNATURES,'__cudaRegisterVar':'void(ptr_ptr,char_ptr,char_ptr,const_char_ptr,i32,size,i32,i32)'}
SYMBOL_SIGNATURES = {
    "cudaGetSymbolAddress":"i32(out_ptr,const_ptr)",
    "cudaGetSymbolSize":"i32(size_ptr,const_ptr)",
    "cudaMemcpyToSymbol":"i32(const_ptr,const_ptr,size,size,i32)",
    "cudaMemcpyFromSymbol":"i32(ptr,const_ptr,size,size,i32)",
}
SIGNATURES = {**REGISTRATION_SIGNATURES, **SYMBOL_SIGNATURES}


def validate(value):
    errors = []
    if not isinstance(value, dict) or set(value) != {'schema_version','dll_name','exports','limits'}:
        return ['invalid Runtime profile fields']
    if value['schema_version'] != 1 or value['dll_name'] != 'cudart64_12.dll': errors.append('invalid identity')
    if not isinstance(value['limits'], list) or not value['limits']: errors.append('missing limits')
    entries = value['exports']
    if not isinstance(entries, list): return errors + ['invalid exports']
    seen = set()
    for item in entries:
        if not isinstance(item, dict) or set(item) != {'symbol','signature_id','behavior','test_ids'}:
            errors.append('invalid export fields'); continue
        symbol = item['symbol']
        if not isinstance(symbol, str): errors.append('invalid symbol'); continue
        if symbol in seen or SIGNATURES.get(symbol) != item['signature_id']: errors.append('ABI drift')
        seen.add(symbol)
        if not isinstance(item['behavior'], str) or not item['behavior']: errors.append('missing behavior')
        refs = item['test_ids']
        if not isinstance(refs, list) or not refs: errors.append('missing tests'); continue
        for ref in refs:
            if not isinstance(ref,str): errors.append('invalid test reference'); continue
            file, sep, test = ref.partition('#')
            path = PurePosixPath(file)
            if not sep or not test or path.is_absolute() or '..' in path.parts or '\\' in file or ':' in file:
                errors.append('escaped test reference'); continue
            target = REPO / file
            if not target.is_file() or test not in target.read_text(encoding='utf-8'):
                errors.append('missing test reference')
    if seen != set(SIGNATURES) or len(entries) != 26: errors.append('incomplete exports')
    header = (REPO / 'include/ct_cudart.h').read_text()
    if set(re.findall(r'CT_RUNTIME_API ((?:__cuda|cuda)\w+)\(',header)) != set(SIGNATURES): errors.append('header drift')
    exports=(REPO/'tests/p09a_runtime.def').read_text().splitlines()[2:]
    if len(exports)!=26 or set(exports)!=set(SIGNATURES):errors.append('import library drift')
    return errors

def main():
    errors = validate(json.loads((REPO / PROFILE).read_text()))
    for error in errors: print(error)
    if not errors: print('Runtime profile: 26 bounded declarations checked; execution unproven')
    return bool(errors)

if __name__ == '__main__': raise SystemExit(main())
