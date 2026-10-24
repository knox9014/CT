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
fn global_pointer(t: Ty) -> u32 {
    match t {
        Ty::F32 => 8,
        Ty::U32 => 15,
        Ty::U64 => 16,
        Ty::Pred => unreachable!(),
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
    module_globals: BTreeMap<String, u32>,
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
            Value::Global(n) => self.result(117, 4, &[self.module_globals[n]]),
            Value::Bits(t, b) => self.constant(*t, *b),
            Value::Builtin(kind, component) => {
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
                let scalar = self.result(81, 4, &[vec, *component]);
                self.result(113, 3, &[scalar])
            }
        }
    }
    fn address(&mut self, v: &Value, offset: u64, t: Ty) -> u32 {
        if let Value::Global(n) = v {
            return self.module_globals[n];
        }
        let mut addr = self.read(v, Ty::U64);
        if offset != 0 {
            let off = self.constant(Ty::U64, offset);
            addr = self.result(128, 4, &[addr, off]);
        }
        self.result(120, global_pointer(t), &[addr])
    }
    fn operation(&mut self, op: Op, t: Ty, args: &[Value]) -> u32 {
        let ids: Vec<u32> = args
            .iter()
            .enumerate()
            .map(|(i, v)| {
                self.read(
                    v,
                    if matches!(op, Op::Shl | Op::Shr | Op::SignedShr) && i == 1 {
                        Ty::U32
                    } else if op == Op::Select && i == 2 {
                        Ty::Pred
                    } else {
                        t
                    },
                )
            })
            .collect();
        let is_float = t == Ty::F32;
        let tid = type_id(t);
        match op {
            Op::Mov | Op::Cvta => ids[0],
            Op::Convert { to, signed } => {
                if to == t {
                    return ids[0];
                }
                if signed && t == Ty::U32 && to == Ty::U64 {
                    self.result(114, 4, &[ids[0]])
                } else {
                    self.result(113, type_id(to), &ids)
                }
            }
            Op::And => self.result(199, tid, &ids),
            Op::Or => self.result(197, tid, &ids),
            Op::Xor => self.result(198, tid, &ids),
            Op::Not => self.result(200, tid, &ids),
            Op::Shl | Op::Shr | Op::SignedShr => {
                let width = if t == Ty::U64 { 64 } else { 32 };
                let limit = self.constant(Ty::U32, width);
                let max_shift = self.constant(Ty::U32, width - 1);
                let oversized = self.result(174, 2, &[ids[1], limit]);
                // SPIR-V shifts must never see counts >= the base bit width.
                let safe = self.result(169, 3, &[oversized, max_shift, ids[1]]);
                // Keep PTX counts U32, then normalize the bounded count to the
                // base width for the native compiler's integer shift lowering.
                let safe = if t == Ty::U64 {
                    self.result(113, 4, &[safe])
                } else {
                    safe
                };
                if op == Op::SignedShr {
                    self.result(195, tid, &[ids[0], safe])
                } else {
                    let shifted =
                        self.result(if op == Op::Shl { 196 } else { 194 }, tid, &[ids[0], safe]);
                    let zero = self.constant(t, 0);
                    self.result(169, tid, &[oversized, zero, shifted])
                }
            }
            Op::Add => self.result(if is_float { 129 } else { 128 }, tid, &ids),
            Op::Sub => self.result(if is_float { 131 } else { 130 }, tid, &ids),
            Op::Mul => self.result(if is_float { 133 } else { 132 }, tid, &ids),
            Op::MulWide => {
                let a = self.result(113, 4, &[ids[0]]);
                let b = self.result(113, 4, &[ids[1]]);
                self.result(132, 4, &[a, b])
            }
            Op::SignedMulWide => {
                let a = self.result(114, 4, &[ids[0]]);
                let b = self.result(114, 4, &[ids[1]]);
                self.result(132, 4, &[a, b])
            }
            Op::Mad => {
                let product = self.result(132, tid, &ids[..2]);
                self.result(128, tid, &[product, ids[2]])
            }
            Op::Div => self.result(134, tid, &ids),
            Op::Rem => self.result(137, tid, &ids),
            Op::Min { signed } | Op::Max { signed } => {
                let less = self.result(if signed { 177 } else { 176 }, 2, &ids);
                let (yes, no) = if matches!(op, Op::Min { .. }) {
                    (ids[0], ids[1])
                } else {
                    (ids[1], ids[0])
                };
                self.result(169, tid, &[less, yes, no])
            }
            Op::Neg | Op::Abs => {
                let zero = self.constant(t, 0);
                let negated = self.result(130, tid, &[zero, ids[0]]);
                if op == Op::Neg {
                    negated
                } else {
                    let negative = self.result(177, 2, &[ids[0], zero]);
                    self.result(169, tid, &[negative, negated, ids[0]])
                }
            }
            Op::Ge => self.result(if is_float { 190 } else { 174 }, 2, &ids),
            Op::SignedGe | Op::SignedLt | Op::SignedGt | Op::SignedLe => {
                let opcode = match op {
                    Op::SignedGe => 175,
                    Op::SignedLt => 177,
                    Op::SignedGt => 173,
                    Op::SignedLe => 179,
                    _ => unreachable!(),
                };
                self.result(opcode, 2, &ids)
            }
            Op::Lt => self.result(if is_float { 184 } else { 176 }, 2, &ids),
            Op::Eq => self.result(170, 2, &ids),
            Op::Ne => self.result(171, 2, &ids),
            Op::Gt => self.result(172, 2, &ids),
            Op::Le => self.result(178, 2, &ids),
            Op::Select => self.result(169, tid, &[ids[2], ids[0], ids[1]]),
        }
    }
}
pub(super) fn generate(k: &Kernel) -> Result<Vec<u8>, Error> {
    generate_module(std::slice::from_ref(k))
}
pub(super) fn generate_module(kernels: &[Kernel]) -> Result<Vec<u8>, Error> {
    let Some(first) = kernels.first() else {
        return Err(Error {
            line: 1,
            unsupported: false,
            message: "missing entry",
        });
    };
    if kernels.iter().any(|k| k.globals != first.globals) {
        return Err(Error {
            line: 1,
            unsupported: true,
            message: "inconsistent module globals",
        });
    }

    let mut w = Writer {
        next: 17,
        types: vec![],
        globals: vec![],
        annotations: vec![],
        body: vec![],
        constants: BTreeMap::new(),
        builtins: BTreeMap::new(),
        registers: BTreeMap::new(),
        module_globals: BTreeMap::new(),
        signatures: BTreeMap::new(),
        current_builtins: BTreeSet::new(),
    };
    inst(&mut w.types, 19, &[1]);
    inst(&mut w.types, 20, &[2]);
    inst(&mut w.types, 21, &[3, 32, 0]);
    inst(&mut w.types, 21, &[4, 64, 0]);
    // Kernel requires Signedness 0 on every OpTypeInt. Signed interpretation is
    // carried by OpSConvert / signed compare / arithmetic-shift opcodes.
    inst(&mut w.types, 22, &[5, 32]);
    inst(&mut w.types, 23, &[6, 4, 3]);
    inst(&mut w.types, 32, &[7, 1, 6]);
    inst(&mut w.types, 32, &[8, 5, 5]);
    inst(&mut w.types, 32, &[15, 5, 3]);
    inst(&mut w.types, 32, &[16, 5, 4]);
    for t in [Ty::Pred, Ty::U32, Ty::U64, Ty::F32] {
        inst(&mut w.types, 32, &[register_pointer(t), 7, type_id(t)]);
    }
    for global in first.globals.iter() {
        if let GlobalStorage::MutableU32 { initializer } = global.storage {
            let constant = w.constant(Ty::U32, initializer as u64);
            let id = w.id();
            inst(&mut w.globals, 59, &[15, id, 5, constant]);
            let mut linkage = vec![id, 41];
            linkage.extend(string_words(&global.name));
            linkage.push(0); // LinkageType Export
            inst(&mut w.annotations, 71, &linkage);
            w.module_globals.insert(global.name.clone(), id);
        }
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
    if !w.module_globals.is_empty() {
        inst(&mut out, 17, &[5]);
    }
    inst(&mut out, 14, &[2, 2]);
    for entry in &entries {
        inst(&mut out, 15, entry);
    }
    // PTX .rn operations must not be contracted across instructions. Kernel
    // uses ContractionOff; NoContraction decoration requires Shader capability.
    for entry in entries {
        inst(&mut out, 16, &[entry[1], 31]);
    }
    out.extend(w.annotations);
    out.extend(w.types);
    out.extend(w.globals);
    out.extend(w.body);
    Ok(out.into_iter().flat_map(u32::to_le_bytes).collect())
}

fn generate_kernel(w: &mut Writer, k: &Kernel) -> u32 {
    w.registers.clear();
    w.current_builtins.clear();
    let types: Vec<u32> = k
        .params
        .iter()
        .map(|p| match p.kind {
            ParamKind::Pointer => {
                if p.alignment == 8 {
                    16
                } else {
                    8
                }
            }
            ParamKind::U32 => 3,
            ParamKind::U64 => 4,
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
                    ty,
                    dst,
                    address,
                    offset,
                    volatile,
                } => {
                    let ptr = w.address(address, *offset, *ty);
                    let id = w.result(
                        61,
                        type_id(*ty),
                        &[
                            ptr,
                            if *volatile { 3 } else { 2 },
                            if *ty == Ty::U64 { 8 } else { 4 },
                        ],
                    );
                    inst(&mut w.body, 62, &[w.registers[dst], id]);
                }
                InstructionKind::Store {
                    ty,
                    address,
                    offset,
                    value,
                    volatile,
                } => {
                    let ptr = w.address(address, *offset, *ty);
                    let id = w.read(value, *ty);
                    inst(
                        &mut w.body,
                        62,
                        &[
                            ptr,
                            id,
                            if *volatile { 3 } else { 2 },
                            if *ty == Ty::U64 { 8 } else { 4 },
                        ],
                    );
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

#[cfg(test)]
mod global_tests {
    use super::*;
    #[test]
    fn rejects_inconsistent_module_global_tables() {
        let source = ".version 8.0\n.target sm_52\n.address_size 64\n.global .align 4 .u32 g=7; .entry first() { ret; } .entry second() { ret; }";
        let mut m = ct_ptx::parse_module(source).unwrap();
        m.kernels[1].globals = Arc::from([]);
        assert!(generate_module(&m.kernels).unwrap_err().unsupported);
    }
}
