//! SPIR-V 1.0 Kernel/OpenCL/Physical64. Opcode/enumerant definitions checked
//! against Khronos SPIRV-Headers vulkan-sdk-1.4.328.1, not inferred from PTX names.
use super::*;
use std::collections::BTreeSet;
fn inst(target: &mut Vec<u32>, opcode: u32, operands: &[u32]) {
    target.push(((operands.len() as u32 + 1) << 16) | opcode);
    target.extend(operands);
}
fn string_words(text: &str) -> Vec<u32> {
    let mut b = text.as_bytes().to_vec();
    b.push(0);
    while !b.len().is_multiple_of(4) {
        b.push(0);
    }
    b.chunks_exact(4)
        .map(|v| u32::from_le_bytes(v.try_into().unwrap()))
        .collect()
}
fn type_id(t: Ty) -> u32 {
    match t {
        Ty::Pred => 2,
        Ty::U32 => 3,
        Ty::U64 => 4,
        Ty::F32 => 5,
    }
}
fn register_pointer(t: Ty) -> u32 {
    match t {
        Ty::Pred => 9,
        Ty::U32 => 10,
        Ty::U64 => 11,
        Ty::F32 => 12,
    }
}
struct Writer {
    next: u32,
    types: Vec<u32>,
    globals: Vec<u32>,
    annotations: Vec<u32>,
    body: Vec<u32>,
    constants: BTreeMap<(Ty, u64), u32>,
    builtins: BTreeMap<u32, u32>,
    registers: BTreeMap<String, u32>,
    signatures: BTreeMap<Vec<u32>, u32>,
    current_builtins: BTreeSet<u32>,
}
impl Writer {
    fn id(&mut self) -> u32 {
        let id = self.next;
        self.next += 1;
        id
    }
    fn result(&mut self, op: u32, t: u32, args: &[u32]) -> u32 {
        let id = self.id();
        let mut operands = vec![t, id];
        operands.extend(args);
        inst(&mut self.body, op, &operands);
        id
    }
    fn constant(&mut self, t: Ty, bits: u64) -> u32 {
        if let Some(&id) = self.constants.get(&(t, bits)) {
            return id;
        }
        let id = self.id();
        let mut words = vec![type_id(t), id, bits as u32];
        if t == Ty::U64 {
            words.push((bits >> 32) as u32);
        }
        inst(&mut self.types, 43, &words);
        self.constants.insert((t, bits), id);
        id
    }
    fn read(&mut self, v: &Value, t: Ty) -> u32 {
        match v {
            Value::Reg(n) => self.result(61, type_id(t), &[self.registers[n]]),
            Value::Bits(t, b) => self.constant(*t, *b),
            Value::Builtin(kind) => {
                let variable = if let Some(&id) = self.builtins.get(kind) {
                    id
                } else {
                    let id = self.id();
                    inst(&mut self.globals, 59, &[7, id, 1]);
                    inst(&mut self.annotations, 71, &[id, 11, *kind]);
                    self.builtins.insert(*kind, id);
                    id
                };
                self.current_builtins.insert(variable);
                let vec = self.result(61, 6, &[variable]);
                let x = self.result(81, 4, &[vec, 0]);
                self.result(113, 3, &[x])
            }
        }
    }
    fn address(&mut self, v: &Value, offset: u64) -> u32 {
        let mut addr = self.read(v, Ty::U64);
        if offset != 0 {
            let off = self.constant(Ty::U64, offset);
            addr = self.result(128, 4, &[addr, off]);
        }
        self.result(120, 8, &[addr])
    }
    fn operation(&mut self, op: Op, t: Ty, args: &[Value]) -> u32 {
        let ids: Vec<u32> = args
            .iter()
            .enumerate()
            .map(|(i, v)| {
                self.read(
                    v,
                    if op == Op::Select && i == 2 {
                        Ty::Pred
                    } else {
                        t
                    },
                )
            })
            .collect();
        let is_float = t == Ty::F32;
        let tid = type_id(t);
        let id = match op {
            Op::Mov | Op::Cvta => return ids[0],
            Op::Add => self.result(if is_float { 129 } else { 128 }, tid, &ids),
            Op::Sub => self.result(if is_float { 131 } else { 130 }, tid, &ids),
            Op::Mul => self.result(if is_float { 133 } else { 132 }, tid, &ids),
            Op::MulWide => {
                let a = self.result(113, 4, &[ids[0]]);
                let b = self.result(113, 4, &[ids[1]]);
                self.result(132, 4, &[a, b])
            }
            Op::SignedMulWide => {
                let a = self.result(124, 13, &[ids[0]]);
                let b = self.result(124, 13, &[ids[1]]);
                let a = self.result(114, 14, &[a]);
                let b = self.result(114, 14, &[b]);
                let product = self.result(132, 14, &[a, b]);
                self.result(124, 4, &[product])
            }
            Op::Mad => {
                let product = self.result(132, 3, &ids[..2]);
                self.result(128, 3, &[product, ids[2]])
            }
            Op::Div => self.result(134, tid, &ids),
            Op::Rem => self.result(137, tid, &ids),
            Op::Ge => self.result(if is_float { 190 } else { 174 }, 2, &ids),
            Op::SignedGe | Op::SignedLt => {
                let a = self.result(124, 13, &[ids[0]]);
                let b = self.result(124, 13, &[ids[1]]);
                self.result(if op == Op::SignedGe { 175 } else { 177 }, 2, &[a, b])
            }
            Op::Lt => self.result(if is_float { 184 } else { 176 }, 2, &ids),
            Op::Eq => self.result(170, 2, &ids),
            Op::Select => self.result(169, tid, &[ids[2], ids[0], ids[1]]),
        };
        if is_float && matches!(op, Op::Add | Op::Sub | Op::Mul) {
            inst(&mut self.annotations, 71, &[id, 42]);
        }
        id
    }
}
pub(super) fn generate(k: &Kernel) -> Vec<u8> {
    generate_module(std::slice::from_ref(k))
}
pub(super) fn generate_module(kernels: &[Kernel]) -> Vec<u8> {
    let mut w = Writer {
        next: 15,
        types: vec![],
        globals: vec![],
        annotations: vec![],
        body: vec![],
        constants: BTreeMap::new(),
        builtins: BTreeMap::new(),
        registers: BTreeMap::new(),
        signatures: BTreeMap::new(),
        current_builtins: BTreeSet::new(),
    };
    inst(&mut w.types, 19, &[1]);
    inst(&mut w.types, 20, &[2]);
    inst(&mut w.types, 21, &[3, 32, 0]);
    inst(&mut w.types, 21, &[4, 64, 0]);
    inst(&mut w.types, 21, &[13, 32, 1]);
    inst(&mut w.types, 21, &[14, 64, 1]);
    inst(&mut w.types, 22, &[5, 32]);
    inst(&mut w.types, 23, &[6, 4, 3]);
    inst(&mut w.types, 32, &[7, 1, 6]);
    inst(&mut w.types, 32, &[8, 5, 5]);
    for t in [Ty::Pred, Ty::U32, Ty::U64, Ty::F32] {
        inst(&mut w.types, 32, &[register_pointer(t), 7, type_id(t)]);
    }
    let mut entries = Vec::new();
    for kernel in kernels {
        let function = generate_kernel(&mut w, kernel);
        let mut entry = vec![6, function];
        entry.extend(string_words(&kernel.name));
        entry.extend(&w.current_builtins);
        entries.push(entry);
    }
    let mut out = vec![0x07230203, 0x00010000, 0, w.next, 0];
    for cap in [4, 6, 11] {
        inst(&mut out, 17, &[cap]);
    }
    inst(&mut out, 14, &[2, 2]);
    for entry in entries {
        inst(&mut out, 15, &entry);
    }
    out.extend(w.annotations);
    out.extend(w.types);
    out.extend(w.globals);
    out.extend(w.body);
    out.into_iter().flat_map(u32::to_le_bytes).collect()
}

fn generate_kernel(w: &mut Writer, k: &Kernel) -> u32 {
    w.registers.clear();
    w.current_builtins.clear();
    let types: Vec<u32> = k
        .params
        .iter()
        .map(|p| match p.kind {
            ParamKind::Pointer => 8,
            ParamKind::U32 => 3,
            ParamKind::F32 => 5,
        })
        .collect();
    let signature = if let Some(&id) = w.signatures.get(&types) {
        id
    } else {
        let id = w.id();
        let mut sig = vec![id, 1];
        sig.extend(&types);
        inst(&mut w.types, 33, &sig);
        w.signatures.insert(types.clone(), id);
        id
    };
    let function = w.id();
    inst(&mut w.body, 54, &[1, function, 0, signature]);
    let mut parameters = Vec::new();
    for t in types {
        let id = w.id();
        inst(&mut w.body, 55, &[t, id]);
        parameters.push(id);
    }
    for n in k.registers.keys() {
        let id = w.id();
        w.registers.insert(n.clone(), id);
    }
    let labels: Vec<u32> = k.blocks.iter().map(|_| w.id()).collect();
    for (i, b) in k.blocks.iter().enumerate() {
        inst(&mut w.body, 248, &[labels[i]]);
        if i == 0 {
            for (n, &t) in &k.registers {
                inst(&mut w.body, 59, &[register_pointer(t), w.registers[n], 7]);
            }
        }
        for instruction in &b.instructions {
            match &instruction.kind {
                InstructionKind::Param { dst, index } => {
                    let id = if k.params[*index].kind == ParamKind::Pointer {
                        w.result(117, 4, &[parameters[*index]])
                    } else {
                        parameters[*index]
                    };
                    inst(&mut w.body, 62, &[w.registers[dst], id]);
                }
                InstructionKind::Compute { dst, op, ty, args } => {
                    let id = w.operation(*op, *ty, args);
                    inst(&mut w.body, 62, &[w.registers[dst], id]);
                }
                InstructionKind::Load {
                    dst,
                    address,
                    offset,
                } => {
                    let ptr = w.address(address, *offset);
                    let id = w.result(61, 5, &[ptr]);
                    inst(&mut w.body, 62, &[w.registers[dst], id]);
                }
                InstructionKind::Store {
                    address,
                    offset,
                    value,
                } => {
                    let ptr = w.address(address, *offset);
                    let id = w.read(value, Ty::F32);
                    inst(&mut w.body, 62, &[ptr, id]);
                }
            }
        }
        match &b.terminator {
            Terminator::Return => inst(&mut w.body, 253, &[]),
            Terminator::Jump(t) => inst(&mut w.body, 249, &[labels[*t]]),
            Terminator::Branch {
                predicate,
                negated,
                target,
                otherwise,
            } => {
                let mut p = w.read(&Value::Reg(predicate.clone()), Ty::Pred);
                if *negated {
                    p = w.result(168, 2, &[p]);
                }
                inst(&mut w.body, 250, &[p, labels[*target], labels[*otherwise]]);
            }
        }
    }
    inst(&mut w.body, 56, &[]);
    function
}
