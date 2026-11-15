"""Independent staged-loop oracle and exact genuine fixture SPIR-V checks."""
import struct
from block_barrier_check import decode

def validate_result(value,seed):
    if type(seed) is not int or not 1<=seed<=1000000:return False
    if (type(value) is not dict or set(value)!={'status','seed','integers','floats'}
            or value['status']!='pass' or type(value['seed']) is not int or value['seed']!=seed):return False
    if any(type(value[key]) is not list or len(value[key])!=3 for key in ('integers','floats')):return False
    for mode,(threads,blocks,rounds) in enumerate(((64,2,0),(64,3,3),(128,4,5))):
        ints=value['integers'][mode];floats=value['floats'][mode];n=threads*blocks
        if type(ints) is not list or type(floats) is not list or len(ints)!=n or len(floats)!=n:return False
        for block in range(blocks):
            iv=[(seed*7919+(block*threads+t)*1237)&0xffffffff for t in range(threads)]
            fv=[float(seed%997+block*threads+t) for t in range(threads)]
            for _ in range(rounds):
                first=[v^0xa5a55a5a for v in iv];ff=[v+1 for v in fv]
                second=[(first[(t+1)%threads]+17)&0xffffffff for t in range(threads)];sf=[ff[(t+1)%threads]+2 for t in range(threads)]
                iv=[second[(t+1)%threads]^0x3c3c3c3c for t in range(threads)];fv=[sf[(t+1)%threads]+4 for t in range(threads)]
            for t in range(threads):
                i=block*threads+t
                if type(ints[i]) is not int or ints[i]!=(iv[t]+29)&0xffffffff:return False
                if type(floats[i]) is not float or floats[i]!=fv[t]+8:return False
    return True

def inspect_spirv(data):
    _,ops=decode(data)
    uints={a[0] for op,a,_ in ops if op==21 and a[1:]==[32,0]}
    constants={a[1]:a[2] for op,a,_ in ops if op==43 and len(a)==3 and a[0] in uints}
    arrays={a[0]:a[1:] for op,a,_ in ops if op==28 and len(a)==3}
    pointers={a[0]:a[1:] for op,a,_ in ops if op==32 and len(a)==3}
    objects={a[1]:a[0] for op,a,_ in ops if op==59 and len(a)==3 and a[2]==4}
    entries={a[1] for op,a,_ in ops if op==15 and a[0]==6}
    if len(objects)!=4 or len(entries)!=2:raise ValueError('expected shared fixture entries/objects')
    for obj,ptr in objects.items():
        storage,array=pointers[ptr]
        if storage!=4 or arrays[array][0] not in uints or constants.get(arrays[array][1])!=128:raise ValueError('Workgroup U32 array extent/type')
        if not any(op==71 and a==[obj,44,4] for op,a,_ in ops):raise ValueError('shared alignment')
    functions={};current=block=None;used={};addresses={};loads=stores=bitcasts=0
    for op,a,_ in ops:
        if op==54:
            current=a[1];functions[current]=dict(labels=[],edges={},barriers=0,returns=0,params=[]);used[current]={}
        if op==55:functions[current]['params'].append(a[0])
        if op==248:block=a[0];functions[current]['labels'].append(block)
        if op in (249,250,253):
            if current is None or block is None or block in functions[current]['edges']:raise ValueError('terminator ownership')
            functions[current]['edges'][block]=[] if op==253 else list(a if op==249 else a[1:])
            if op==253:functions[current]['returns']+=1
        if op==56:current=block=None
        if op==224:
            if current is None or len(a)!=3 or [constants.get(v) for v in a]!=[2,2,0x310]:raise ValueError('CTA barrier scope/semantics')
            functions[current]['barriers']+=1
        if op in (57,225,254,255):raise ValueError('unexpected call/memory-only barrier/exit')
        if op==65:
            if current is None or len(a)!=4 or a[2] not in objects or pointers.get(a[0]) not in ([4,u] for u in uints):raise ValueError('shared AccessChain')
            addresses[a[1]]=current;used[current][a[2]]=used[current].get(a[2],0)+1
        if op==61 and len(a)>2 and a[2] in addresses:
            if len(a)!=5 or a[0] not in uints or a[3:]!=[3,4] or addresses[a[2]]!=current:raise ValueError('volatile shared U32 load')
            loads+=1
        if op==62 and a and a[0] in addresses:
            if len(a)!=4 or a[2:]!=[3,4] or addresses[a[0]]!=current:raise ValueError('volatile shared U32 store')
            stores+=1
        if op==124:bitcasts+=1
    if set(functions)!=entries or current is not None:raise ValueError('entry/function identity')
    for f in functions.values():
        labels=f['labels'];edges=f['edges'];positions={v:i for i,v in enumerate(labels)}
        if len(labels)!=5 or set(labels)!=set(edges) or f['barriers']!=3 or f['returns']!=1 or len(f['params'])!=3 or f['params'][-1] not in uints:raise ValueError('fixture CFG/ABI shape')
        if sorted(map(len,edges.values()))!=[0,1,1,2,2] or any(t not in positions for targets in edges.values() for t in targets):raise ValueError('fixture CFG targets')
        if sum(positions[t]<=positions[b] for b,targets in edges.items() for t in targets)!=1:raise ValueError('fixture loop backedge')
        if any(len(targets)==2 and targets[0]==targets[1] for targets in edges.values()):raise ValueError('erased conditional branch')
    sets=[set(counts) for counts in used.values()]
    if (len(sets)!=2 or sets[0]&sets[1] or set.union(*sets)!=set(objects)
            or any(sorted(counts.values())!=[2,2] for counts in used.values()) or (loads,stores,bitcasts)!=(4,4,4)):raise ValueError('shared access identity/count')
    return dict(entries=2,blocks_per_entry=5,conditional_branches_per_entry=2,loop_backedges_per_entry=1,barriers_per_entry=3,shared_objects=4,shared_bytes_per_entry=1024,shared_loads=loads,shared_stores=stores,f32_bitcasts=bitcasts,barrier_semantics=0x310)

def erased_loop(data):
    """Offline mutation only: replace loop true edge with its exit edge."""
    words,ops=decode(data);seen=set()
    for op,a,i in ops:
        if op==54:seen=set()
        if op==248:seen.add(a[0])
        if op==250 and a[1] in seen:
            words[i+2]=a[2]
            return struct.pack('<'+'I'*len(words),*words)
    raise ValueError('loop mutation target missing')
