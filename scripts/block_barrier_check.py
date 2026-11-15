"""Independent integer oracle and exact structural checks, not a validator mock."""
import struct

def validate_result(value,seed):
    if type(seed) is not int or not 1<=seed<=1000000:return False
    if (type(value) is not dict or set(value)!={'status','seed','results'} or value['status']!='pass'
            or type(value['seed']) is not int or value['seed']!=seed or type(value['results']) is not list or len(value['results'])!=2):return False
    for row,(threads,blocks) in zip(value['results'],((64,3),(128,4))):
        if type(row) is not list or len(row)!=threads*blocks:return False
        for i,actual in enumerate(row):
            index=(i//threads)*threads+(i%threads+2)%threads
            source=(seed*7919+index*1237)&0xffffffff
            expected=(((((source^0xa5a55a5a)+17)&0xffffffff)^0x3c3c3c3c)+29)&0xffffffff
            if type(actual) is not int or actual!=expected:return False
    return True

def decode(data):
    if len(data)<20 or len(data)%4:raise ValueError('SPIR-V length')
    words=list(struct.unpack('<'+'I'*(len(data)//4),data))
    if words[0]!=0x07230203:raise ValueError('SPIR-V magic')
    ops=[];i=5
    while i<len(words):
        n=words[i]>>16
        if n==0 or i+n>len(words):raise ValueError('SPIR-V instruction length')
        ops.append((words[i]&65535,words[i+1:i+n],i));i+=n
    return words,ops

def inspect_spirv(data):
    _,ops=decode(data);types={};constants={};entries=set();functions={};current=None;barriers=[]
    for op,a,_ in ops:
        if op==21 and len(a)==3:types[a[0]]=(a[1],a[2])
        if op==43 and len(a)==3:
            if a[1] in constants:raise ValueError('duplicate constant')
            constants[a[1]]=(a[0],a[2])
        if op==15:
            if len(a)<3 or a[0]!=6 or a[1] in entries:raise ValueError('Kernel entry')
            entries.add(a[1])
        if op==54:
            if current is not None or len(a)!=4 or a[1] in functions:raise ValueError('function')
            current=a[1];functions[current]=[0,0,0]
        if op==248:
            if current is None:raise ValueError('label outside function')
            functions[current][1]+=1
        if op==253:
            if current is None:raise ValueError('return outside function')
            functions[current][2]+=1
        if op in (57,246,247,249,250,251,254,255):raise ValueError('nonlinear/calling barrier module')
        if op==224:
            if current is None or len(a)!=3:raise ValueError('control barrier arity')
            values=[]
            for i in a:
                if i not in constants or types.get(constants[i][0])!=(32,0):raise ValueError('barrier operand must be constant U32')
                values.append(constants[i][1])
            if values!=[2,2,0x310]:raise ValueError('barrier scope or memory semantics')
            functions[current][0]+=1;barriers.append(values)
        if op==225:raise ValueError('memory-only barrier is not rendezvous')
        if op==56:
            if current is None:raise ValueError('end outside function')
            current=None
    if current is not None or len(entries)!=2 or entries!=set(functions) or list(functions.values())!=[[3,1,1],[3,1,1]]:raise ValueError('barrier function/control shape')
    return dict(barriers=len(barriers),per_function=[f[0] for f in functions.values()],execution_scope=2,memory_scope=2,semantics=0x310)

def invalid_execution_scope(data):
    words,ops=decode(data)
    u32=next((a[0] for op,a,_ in ops if op==21 and a[1:]==[32,0]),None)
    first=next((i for op,_,i in ops if op==224),None)
    function=next((i for op,_,i in ops if op==54),None)
    if u32 is None or first is None or function is None:raise ValueError('control mutation input')
    new=words[3];words[3]=new+1;words[first+1]=new
    words[function:function]=[(4<<16)|43,u32,new,4] # Invocation scope does not implement the required CTA rendezvous.
    return struct.pack('<'+'I'*len(words),*words)
