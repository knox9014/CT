"""Check the closed Runtime ABI contract; this is not execution evidence."""
import json
from pathlib import Path, PurePosixPath
import re

REPO = Path(__file__).resolve().parents[1]
PROFILE = 'docs/compatibility/runtime-profile-v1.json'
SIGNATURES = {
    'cudaGetDeviceCount':'i32(out_i32)', 'cudaGetDevice':'i32(out_i32)',
    'cudaSetDevice':'i32(i32)', 'cudaDeviceSynchronize':'i32()',
    'cudaMalloc':'i32(out_ptr,size)', 'cudaFree':'i32(ptr)',
    'cudaMemcpy':'i32(ptr,const_ptr,size,i32)', 'cudaMemset':'i32(ptr,i32,size)',
    'cudaGetLastError':'i32()', 'cudaPeekAtLastError':'i32()',
    'cudaGetErrorName':'const_char_ptr(i32)', 'cudaGetErrorString':'const_char_ptr(i32)',
    'cudaDriverGetVersion':'i32(out_i32)', 'cudaRuntimeGetVersion':'i32(out_i32)',
}

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
    if seen != set(SIGNATURES) or len(entries) != 14: errors.append('incomplete exports')
    header = (REPO / 'include/ct_cudart.h').read_text()
    if set(re.findall(r'CT_RUNTIME_API (cuda\w+)\(',header)) != set(SIGNATURES): errors.append('header drift')
    exports=(REPO/'tests/p09a_runtime.def').read_text().splitlines()[2:]
    if len(exports)!=14 or set(exports)!=set(SIGNATURES):errors.append('import library drift')
    return errors

def main():
    errors = validate(json.loads((REPO / PROFILE).read_text()))
    for error in errors: print(error)
    if not errors: print('Runtime profile: 14 bounded declarations checked; execution unproven')
    return bool(errors)

if __name__ == '__main__': raise SystemExit(main())
