"""Offline declaration/units checks; never authorizes native table exposure."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

COMMIT='08b19b28b7c334936846b3aeb61a43aef053e9a1'
CUDART='6bd5fb6c5bf4e74a8987d93912fd9df9'
HOOKS='a094798c2e742e7493f20800200c0a66'
SOURCES={'dark_api/src/lib.rs':'e1c4a6ce02631ec13b2be7f08c9c4682492bf42ed065739ca0777810f0fc47bf',
         'zluda/src/impl/driver.rs':'49a76ea0a43369ccbf122a9a1dec20a2f1abdd7cbdaaa8201350082808e8ca69'}
ARITY={CUDART:{1:2,2:2,4:2,6:5,7:1,8:5,12:0},HOOKS:{2:2,6:2}}
PARAMETERS={CUDART:{1:['CUmodule*','const FatbincWrapper*'],2:['CUcontext*','CUdevice'],4:['CUdevice','u32'],
                    6:['CUmodule*','const FatbincWrapper*','void*','void*','u32'],7:['usize'],
                    8:['const FatbinHeader*','CUmodule*','void*','void*','u32'],12:[]},
            HOOKS:{2:['void**','usize*'],6:['void**','usize*']}}
RUST_TYPES={'*mut cuda_types::cuda::CUmodule':'CUmodule*','*mut cuda_types::cuda::CUcontext':'CUcontext*',
            '*const cuda_types::dark_api::FatbincWrapper':'const FatbincWrapper*',
            '*const cuda_types::dark_api::FatbinHeader':'const FatbinHeader*','cuda_types::cuda::CUdevice':'CUdevice',
            '*mut std::ffi::c_void':'void*','*mut *mut std::ffi::c_void':'void**','*mut usize':'usize*','u32':'u32','usize':'usize'}
NAMES={CUDART:{1:'get_module_from_cubin',2:'cudart_interface_fn2',4:'primary_ctx_retain_with_flags',6:'get_module_from_cubin_ext1',
               7:'cudart_interface_fn7',8:'get_module_from_cubin_ext2',12:'load_compilers'},
       HOOKS:{2:'get_unknown_buffer1',6:'get_unknown_buffer2'}}
EFFECTS={CUDART:{1:'module_load',2:'context',4:'context',6:'module_load',7:'unresolved',8:'module_load',12:'compiler_load'},
         HOOKS:{2:'buffer_query',6:'buffer_query'}}


def validate_inventory(data):
    if (data.get('schema_version')!=1 or type(data.get('schema_version')) is not int
            or data.get('scope')!='offline_table_contract_inventory' or data.get('source_commit')!=COMMIT
            or type(data.get('pointer_bytes')) is not int or data['pointer_bytes']!=8
            or data.get('native_success_authorized') is not False):raise ValueError('inventory scope/pin/word size')
    sources=data.get('sources')
    if not isinstance(sources,list) or len(sources)!=2:raise ValueError('source set')
    if {s.get('path') for s in sources}!=set(SOURCES):raise ValueError('source paths')
    for source in sources:
        path=source['path']
        if source.get('cached_utf8_sha256')!=SOURCES[path] or source.get('url')!='https://github.com/vosen/ZLUDA/blob/'+COMMIT+'/'+path:
            raise ValueError('unpinned primary source')
    tables=data.get('tables')
    if not isinstance(tables,list) or len(tables)!=2 or {t.get('uuid') for t in tables}!={CUDART,HOOKS}:raise ValueError('table identity')
    for table in tables:
        uuid=table['uuid'];count=13 if uuid==CUDART else 7
        name='CUDART_INTERFACE' if uuid==CUDART else 'TOOLS_RUNTIME_CALLBACK_HOOKS'
        if (table.get('source_name')!=name or type(table.get('slot_count')) is not int or table['slot_count']!=count
                or type(table.get('byte_size')) is not int or table['byte_size']!=count*8
                or type(table.get('metadata_slot')) is not int or table['metadata_slot']!=0):raise ValueError('table byte layout')
        fns=table.get('functions');holes=table.get('null_slots')
        if not isinstance(fns,list) or not isinstance(holes,list):raise ValueError('slot lists')
        indexes=[f.get('index') for f in fns]
        if (any(type(i) is not int for i in indexes+holes) or len(set(indexes))!=len(indexes)
                or len(set(holes))!=len(holes) or set(indexes)!=set(ARITY[uuid])
                or set(holes)!=(set(range(1,count))-set(indexes))):raise ValueError('metadata/function/hole overlap')
        for fn in fns:
            i=fn['index'];ret='void' if uuid==HOOKS or i==7 else 'CUresult'
            if (fn.get('return_type')!=ret or fn.get('calling_convention')!='system'
                    or not isinstance(fn.get('argument_types'),list) or len(fn['argument_types'])!=ARITY[uuid][i]
                    or fn['argument_types']!=PARAMETERS[uuid][i]
                    or fn.get('source_name')!=NAMES[uuid][i] or fn.get('effect')!=EFFECTS[uuid][i]
                    or any(type(t) is not str or not t for t in fn['argument_types'])
                    or type(fn.get('source_name')) is not str or not re.fullmatch(r'\w+',fn['source_name'])):raise ValueError('function type')
            if uuid==CUDART and i in (1,6,8) and fn.get('effect')!='module_load':raise ValueError('unguarded private loading route')
        buffers=table.get('buffer_reference')
        expected=[] if uuid==CUDART else [dict(slot=2,element_type='u32',element_count=1024,source_count_unit='elements',runtime_min_reported_count=487),
                                             dict(slot=6,element_type='u32',element_count=14,source_count_unit='elements',runtime_min_reported_count=14)]
        if buffers!=expected or any(type(row[k]) is not int for row in buffers for k in ('slot','element_count','runtime_min_reported_count')):
            raise ValueError('buffer element/byte unit mismatch')
    runtime=data.get('runtime_evidence')
    if (not isinstance(runtime,dict) or runtime.get('kind')!='static_only' or runtime.get('dynamically_observed') is not False
            or runtime.get('buffer_meaning_verified') is not False
            or runtime.get('runtime_sha256')!='760c38928bbe5759f7b31ed6692599eb7ec83cedd5702e84c2b72028a89837e1'
            or runtime.get('disassembly_sha256')!='92309a11965cacaf1384316f3b89b2cf19a514f1fe4a3cae37d1c2e3812a18fb'
            or runtime.get('hooks_query_rva')!='230d6' or runtime.get('getter_call_rvas')!=['22dda','22dfd']):raise ValueError('static Runtime evidence scope')
    return dict(status='inventory_valid',tables=2,callable_slots=9,native_success_authorized=False)


def check_binding(data,uuid,byte_offset,return_type,argument_types,calling_convention):
    validate_inventory(data)
    if type(byte_offset) is not int or byte_offset<0 or byte_offset%8:raise ValueError('aligned byte offset required')
    table=next((t for t in data['tables'] if t['uuid']==uuid),None)
    if table is None:raise ValueError('unknown table')
    slot=byte_offset//8
    fn=next((f for f in table['functions'] if f['index']==slot),None)
    if fn is None:raise ValueError('metadata/null/out-of-range slot is not callable')
    if (return_type,argument_types,calling_convention)!=(fn['return_type'],fn['argument_types'],fn['calling_convention']):raise ValueError('callback signature differs')
    return dict(index=slot,effect=fn['effect'],native_success_authorized=False)


def verify_sources(data,root):
    validate_inventory(data);root=root.resolve();content={}
    for source in data['sources']:
        relative=PurePosixPath(source['path']);path=root.joinpath(*relative.parts)
        if not path.resolve().is_relative_to(root) or not path.is_file():raise ValueError('missing/escaped source')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=source['cached_utf8_sha256']:raise ValueError('source bytes differ')
        content[source['path']]=raw.decode('utf-8')
    declarations=content['dark_api/src/lib.rs']
    for table in data['tables']:
        marker='=> '+table['source_name']+'['+str(table['slot_count'])+'] {'
        if marker not in declarations:raise ValueError('table declaration missing')
        block=declarations.split(marker,1)[1].split('\n    },',1)[0]
        for fn in table['functions']:
            marker='['+str(fn['index'])+'] = '+fn['source_name']+'('
            if marker not in block:raise ValueError('slot declaration missing')
            entry=block.split(marker,1)[1].split(') -> ',1)
            if len(entry)!=2:raise ValueError('return declaration missing')
            # Count argument identifiers, avoiding Rust's :: type separators.
            if len(re.findall(r'\b\w+\s*:(?!:)',entry[0]))!=len(fn['argument_types']):raise ValueError('source argument count')
            args=[' '.join(arg.split(':',1)[1].split()) for arg in entry[0].split(',') if arg.strip()]
            if any(arg not in RUST_TYPES for arg in args) or [RUST_TYPES[arg] for arg in args]!=fn['argument_types']:
                raise ValueError('source argument types')
            wanted='()' if fn['return_type']=='void' else 'cuda_types::cuda::CUresult'
            if not entry[1].startswith(wanted):raise ValueError('source return kind')
    return dict(source_files=2,source_hashes_verified=True,native_success_authorized=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,default=Path(__file__).resolve().parents[1]/'docs/compatibility/bootstrap-tables.json');p.add_argument('--source-root',type=Path);args=p.parse_args()
    data=json.loads(args.inventory.read_text(encoding='utf-8'));result=validate_inventory(data)
    result['primary_sources_verified']=False
    if args.source_root:result.update(verify_sources(data,args.source_root));result['primary_sources_verified']=True
    print(json.dumps(result))
