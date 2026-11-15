"""Exact binary32 integer oracle, independent of host floating-point arithmetic."""
from block_barrier_check import decode
CASES=[(0x3f800001,0x3f7ffffe,0xbf800000),(0x3f800000,0x3f800000,0x33800000),
       (0x3f800001,0x3f800000,0x33800000),(1,0x3f800000,0),(0x00800000,0x3f000000,0),
       (1,0x3f000000,0),(1,0x3f000000,1),(0x7f7fffff,0x40000000,0xff7fffff),
       (0x7f7fffff,0x40000000,0),(0x80000000,0x3f800000,0x80000000),
       (0x3f800000,0x3f800000,0xbf800000),(0x7f800000,0x3f800000,0),
       (0,0x7f800000,0),(0x7f800000,0x3f800000,0xff800000),(0x7fc12345,0x3f800000,0),
       (0x007fffff,0x3f800000,1)]
def nan(v):return (v&0x7f800000)==0x7f800000 and (v&0x7fffff)!=0
def inf(v):return (v&0x7fffffff)==0x7f800000
def finite(v):
    e=(v>>23)&255;m=v&0x7fffff
    return ((-1 if v>>31 else 1)*(m if e==0 else m|0x800000),-149 if e==0 else e-150)
def nearest(n,shift):
    if shift<=0:return n<<(-shift)
    q=n>>shift;r=n-(q<<shift);half=1<<(shift-1)
    return q+int(r>half or (r==half and q&1))
def rounded(n,e,zero_sign=0):
    if n==0:return zero_sign
    sign=0x80000000 if n<0 else 0;n=abs(n);top=n.bit_length()-1+e
    if top < -126:return sign|nearest(n,-149-e)
    mantissa=nearest(n,n.bit_length()-24)
    if mantissa==0x1000000:mantissa>>=1;top+=1
    if top>127:return sign|0x7f800000
    return sign|((top+127)<<23)|(mantissa&0x7fffff)
def fused_bits(a,b,c):
    if any(nan(v) for v in (a,b,c)):return None
    product_sign=(a^b)&0x80000000
    if inf(a) or inf(b):
        if (a&0x7fffffff)==0 or (b&0x7fffffff)==0:return None
        if inf(c) and (c&0x80000000)!=product_sign:return None
        return product_sign|0x7f800000
    if inf(c):return c
    na,ea=finite(a);nb,eb=finite(b);nc,ec=finite(c);ep=ea+eb;e=min(ep,ec)
    total=(na*nb<<(ep-e))+(nc<<(ec-e))
    zero_sign=0x80000000 if na*nb==0 and nc==0 and product_sign and c>>31 else 0
    return rounded(total,e,zero_sign)
def split_bits(a,b,c):
    if nan(a) or nan(b):return None
    if inf(a) or inf(b):
        if (a&0x7fffffff)==0 or (b&0x7fffffff)==0:return None
        p=((a^b)&0x80000000)|0x7f800000
    else:
        na,ea=finite(a);nb,eb=finite(b);p=rounded(na*nb,ea+eb,(a^b)&0x80000000)
    return fused_bits(p,0x3f800000,c)
def matches(actual,expected):
    return type(actual) is int and 0<=actual<=0xffffffff and (nan(actual) if expected is None else actual==expected)
def cases(seed):
    result=list(CASES);state=seed
    for _ in range(16):
        row=[]
        for _ in range(3):
            state^=(state<<13)&0xffffffff;state^=state>>17;state^=(state<<5)&0xffffffff
            row.append(state&0xff7fffff)
        result.append(tuple(row))
    return result
def validate_result(value,seed):
    if type(seed) is not int or not 1<=seed<=1000000:return False
    if type(value) is not dict or set(value)!={'status','seed','cpu_mode','fused','split'} or value['status']!='pass' or type(value['seed']) is not int or value['seed']!=seed or value['cpu_mode'] is not True:return False
    if any(type(value[k]) is not list or len(value[k])!=2 for k in ('fused','split')):return False
    inputs=cases(seed)
    for mode,n in enumerate((192,512)):
        fused=value['fused'][mode];split=value['split'][mode]
        if type(fused) is not list or type(split) is not list or len(fused)!=n or len(split)!=n:return False
        differences=0
        for i in range(n):
            a,b,c=inputs[(i+seed)%32];want=fused_bits(a,b,c);separate=split_bits(a,b,c)
            if not matches(fused[i],want) or not matches(split[i],separate):return False
            differences+=int(want is not None and separate is not None and want!=separate)
        if differences<3:return False
    return True

def inspect_spirv(data):
    _,ops=decode(data)
    imports=[(a,i) for op,a,i in ops if op==11]
    if len(imports)!=1 or b''.join(v.to_bytes(4,'little') for v in imports[0][0][1:]).rstrip(b'\0')!=b'OpenCL.std':raise ValueError('FMA import')
    imported=imports[0][0][0];memory=next(i for op,_,i in ops if op==14)
    if imports[0][1]>=memory:raise ValueError('import layout')
    floats={a[0] for op,a,_ in ops if op==22 and a[1:]==[32]}
    entries={a[1] for op,a,_ in ops if op==15 and a[0]==6}
    modes={a[0] for op,a,_ in ops if op==16 and a[1:]==[31]}
    if len(entries)!=3 or not entries<=modes:raise ValueError('entry/contraction profile')
    functions={};current=None
    for op,a,_ in ops:
        if op==54:current=a[1];functions[current]=[0,0,0,0,0,0]
        if op==56:current=None
        if op in (249,250,251,57,224):raise ValueError('unexpected FMA CFG/call/barrier')
        if op==71 and len(a)>1 and a[1]==40:raise ValueError('fast math')
        if op==12:
            if current is None or len(a)!=7 or a[0] not in floats or a[2]!=imported or a[3]!=26:raise ValueError('must use scalar F32 OpenCL fma26')
            functions[current][0]+=1
        if current is not None:
            for index,code in enumerate((133,129,248,253,55),1):
                if op==code:functions[current][index]+=1
    if set(functions)!=entries or sorted(functions.values())!=sorted([[1,0,0,1,1,4],[1,0,0,1,1,4],[0,1,1,1,1,4]]):raise ValueError('fused/split function shape')
    return dict(entries=3,opencl_imports=1,fma_instructions=2,separate_multiply=1,separate_add=1,contraction_off_entries=3)

def mutate_fma(data,*,semantic):
    """Offline controls only: change fma to mad, or import to undefined ID."""
    import struct
    words,ops=decode(data);first=next(i for op,_,i in ops if op==12)
    words[first+(4 if semantic else 3)]=42 if semantic else words[3]+17
    return struct.pack('<'+'I'*len(words),*words)
