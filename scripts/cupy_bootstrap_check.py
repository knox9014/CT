"""Bounded, CPU-only contracts for the R2 Windows CuPy diagnostic."""
import struct


def import_slots(data):
    """Return SizeOfImage and GetProcAddress IAT RVAs from on-disk PE64 bytes.

    Not a general PE loader. Unsupported/malformed layouts fail closed. No memory
    is dereferenced here; the observer additionally checks the loaded slot value.
    """
    def read(fmt, offset):
        size=struct.calcsize(fmt)
        if offset<0 or offset+size>len(data):raise ValueError('PE bounds')
        return struct.unpack_from(fmt,data,offset)
    try:
        if data[:2]!=b'MZ':raise ValueError('DOS signature')
        pe=read('<I',60)[0]
        if data[pe:pe+4]!=b'PE\0\0':raise ValueError('PE signature')
        machine,count=read('<HH',pe+4)
        optional=pe+24; optional_size=read('<H',pe+20)[0]
        if machine!=0x8664 or not 1<=count<=96 or optional_size<128 or read('<H',optional)[0]!=0x20b:
            raise ValueError('unsupported PE ABI')
        image_size=read('<I',optional+56)[0]
        if not 4096<=image_size<=512*1024*1024 or read('<I',optional+108)[0]<2:
            raise ValueError('PE image size/directories')
        sections=[]
        for i in range(count):
            virtual_size,rva,size,raw=read('<IIII',optional+optional_size+40*i+8)
            if raw+size>len(data) or rva+max(virtual_size,size)>image_size:
                raise ValueError('PE section bounds')
            sections.append((rva,size,raw))
        def offset(rva,size):
            matches=[raw+rva-start for start,length,raw in sections
                     if start<=rva and rva+size<=start+length]
            if len(matches)!=1:raise ValueError('PE RVA bounds/overlap')
            return matches[0]
        def string(rva):
            result=bytearray()
            for i in range(256):
                byte=data[offset(rva+i,1)]
                if byte==0:return bytes(result)
                result.append(byte)
            raise ValueError('PE string bound')
        directory,length=read('<II',optional+120)
        if length<20 or length>20*4096:raise ValueError('PE import size')
        slots=[]
        for d in range(length//20):
            original,time,forwarder,lib,first=read('<IIIII',offset(directory+d*20,20))
            if not any((original,time,forwarder,lib,first)):return image_size,slots
            library=string(lib).lower()
            if not original:raise ValueError('PE original import table missing')
            for i in range(65536):
                entry=read('<Q',offset(original+i*8,8))[0]
                if not entry:break
                if entry>>63:continue
                name=string(entry+2)
                slot=first+i*8
                if slot+8>image_size or slot%8:raise ValueError('PE IAT bounds')
                if name==b'GetProcAddress':
                    if library not in (b'kernel32.dll',b'api-ms-win-core-libraryloader-l1-2-0.dll'):
                        raise ValueError('unsupported loader import')
                    if slot in slots:raise ValueError('duplicate IAT slot')
                    slots.append(slot)
            else:raise ValueError('PE thunk bound')
        raise ValueError('unterminated import descriptors')
    except (struct.error,IndexError,TypeError,OverflowError) as exc:
        raise ValueError('malformed PE') from exc


def expected_words():
    return [struct.unpack('<I',struct.pack('<f',max(0,(3*i-92)/16)))[0] for i in range(64)]


def numerical(words):
    return (type(words) is list and len(words)==64 and all(type(x) is int for x in words)
            and words==expected_words())


def bootstrap_blocker(nominal,observed,*,stage='device_count'):
    """Identify an observed failed bootstrap call, not sole-cause attribution."""
    try:
        keys=('status','stage','error_type','error_code')
        if stage not in ('device_count','input_creation'):return False
        expected=('blocked',stage,'CUDARuntimeError',35)
        return (all(type(nominal[k]) is type(v) and nominal[k]==v for k,v in zip(keys,expected))
                and all(type(observed[k]) is type(nominal[k]) and observed[k]==nominal[k] for k in keys)
                and observed['restored'] is True and type(observed['patches']) is int and observed['patches']>0
                and any(row==dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0)
                        and type(row.get('result')) is int and type(row.get('value')) is int
                        for row in observed['trace']))
    except (TypeError,KeyError,AttributeError):return False
