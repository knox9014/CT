"""Independent all-lane oracle and exact Workgroup storage checks."""
from block_barrier_check import decode,inspect_spirv as inspect_barriers

def validate_result(value,seed):
    if type(seed) is not int or not 1<=seed<=1000000:return False
    if (type(value) is not dict or set(value)!={'status','seed','integers','floats'}
            or value['status']!='pass' or type(value['seed']) is not int or value['seed']!=seed):return False
    if any(type(value[key]) is not list or len(value[key])!=2 for key in ('integers','floats')):return False
    for mode,(threads,blocks) in enumerate(((64,3),(128,4))):
        ints=value['integers'][mode];floats=value['floats'][mode];n=threads*blocks
        if type(ints) is not list or type(floats) is not list or len(ints)!=n or len(floats)!=n:return False
        for i in range(n):
            j=(i//threads)*threads+(i%threads+3)%threads
            original=(seed*7919+j*1237)&0xffffffff
            expected=(((((original^0xa5a55a5a)+17)&0xffffffff)^0x3c3c3c3c)+29)&0xffffffff
            if type(ints[i]) is not int or ints[i]!=expected:return False
            if type(floats[i]) is not float or floats[i]!=float(seed%997+j+15):return False
    return True

def inspect_spirv(data):
    result=inspect_barriers(data);_,ops=decode(data)
    uints={a[0] for op,a,_ in ops if op==21 and a[1:]==[32,0]}
    constants={a[1]:a[2] for op,a,_ in ops if op==43 and len(a)==3 and a[0] in uints}
    arrays={a[0]:a[1:] for op,a,_ in ops if op==28 and len(a)==3}
    pointers={a[0]:a[1:] for op,a,_ in ops if op==32 and len(a)==3}
    objects={a[1]:a[0] for op,a,_ in ops if op==59 and len(a)==3 and a[2]==4}
    if len(objects)!=4:raise ValueError('expected four independent shared objects')
    for obj,ptr in objects.items():
        storage,array=pointers[ptr]
        if storage!=4 or arrays[array][0] not in uints or constants.get(arrays[array][1])!=128:raise ValueError('Workgroup U32 array extent/type')
        if not any(op==71 and a==[obj,44,4] for op,a,_ in ops):raise ValueError('shared alignment')
    current=None;used={};addresses={};loads=stores=bitcasts=0
    for op,a,_ in ops:
        if op==54:current=a[1];used[current]={}
        if op==56:current=None
        if op==65:
            if current is None or len(a)!=4 or a[2] not in objects or pointers.get(a[0]) not in ([4,u] for u in uints):raise ValueError('shared AccessChain')
            addresses[a[1]]=current;used[current][a[2]]=used[current].get(a[2],0)+1
        if op==61 and len(a)>2 and a[2] in addresses:
            if len(a)!=5 or a[0] not in uints or a[3:]!=[3,4] or addresses[a[2]]!=current:raise ValueError('shared volatile U32 load')
            loads+=1
        if op==62 and a and a[0] in addresses:
            if len(a)!=4 or a[2:]!=[3,4] or addresses[a[0]]!=current:raise ValueError('shared volatile U32 store')
            stores+=1
        if op==124:bitcasts+=1
    sets=[set(counts) for counts in used.values()]
    if (len(sets)!=2 or sets[0]&sets[1] or set.union(*sets)!=set(objects)
            or any(sorted(counts.values())!=[2,4] for counts in used.values())
            or (loads,stores,bitcasts)!=(6,6,6)):raise ValueError('shared object ownership/access/bitcasts')
    result.update(shared_objects=4,shared_bytes_per_kernel=1024,shared_loads=loads,shared_stores=stores,f32_bitcasts=bitcasts)
    return result

def invalid_shared_alias(data):
    """Mutate one object root for an offline checker negative; never run on GPU."""
    import struct
    words,ops=decode(data)
    chains=[(a,i) for op,a,i in ops if op==65]
    if not chains:raise ValueError('missing shared access')
    original=chains[0][0][2];other=next(a[2] for a,_ in chains if a[2]!=original)
    words[chains[0][1]+3]=other
    return struct.pack('<'+'I'*len(words),*words)
