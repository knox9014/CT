"""CT-owned native-global feasibility fixture; not CUDA translation or acceptance."""
import argparse,struct
from pathlib import Path

def generate():
    def string(value):
        b=value.encode()+b'\0';b+=bytes((-len(b))%4);return list(struct.unpack('<'+'I'*(len(b)//4),b))
    words=[0x07230203,0x10000,0,13,0]
    def op(code,*args):words.extend([((len(args)+1)<<16)|code,*args])
    for capability in (4,5,6):op(17,capability)
    op(14,2,2);op(15,6,8,*string('ct_global_probe_kernel'));op(71,7,41,*string('ct_global_probe'),0)
    op(19,1);op(21,2,32,0);op(32,3,5,2);op(33,4,1,3);op(43,2,5,7);op(43,2,6,1);op(59,3,7,5,5)
    op(54,1,8,0,4);op(55,3,9);op(248,10);op(61,2,11,7,3,4);op(62,9,11,2,4);op(128,2,12,11,6);op(62,7,12,3,4);op(253);op(56)
    return struct.pack('<'+'I'*len(words),*words)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    root=Path(__file__).resolve().parents[3];output=args.output.resolve()
    if not output.is_relative_to(root/'.cache/p04a-probe'):raise SystemExit('output must remain in configured ignored cache')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(generate())
