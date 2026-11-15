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
    imports: Vec<u32>,
    opencl: Option<u32>,
    globals: Vec<u32>,
    annotations: Vec<u32>,
    body: Vec<u32>,
    constants: BTreeMap<(Ty, u64), u32>,
    builtins: BTreeMap<u32, u32>,
    registers: BTreeMap<String, u32>,
    module_globals: BTreeMap<String, u32>,
    signatures: BTreeMap<Vec<u32>, u32>,
    current_builtins: BTreeSet<u32>,
    shared_pointer: u32,
    shared_objects: Vec<u32>,
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
            Value::Shared(_) => self.constant(t, 0),
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
            Op::Mov | Op::Cvta | Op::CvtaShared => ids[0],
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
            Op::Fma => {
                let set = if let Some(id) = self.opencl {
                    id
                } else {
                    let id = self.id();
                    let mut args = vec![id];
                    args.extend(string_words("OpenCL.std"));
                    inst(&mut self.imports, 11, &args);
                    self.opencl = Some(id);
                    id
                };
                self.result(12, tid, &[set, 26, ids[0], ids[1], ids[2]])
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

    for kernel in kernels {
        for i in kernel.blocks.iter().flat_map(|b| &b.instructions) {
            if let InstructionKind::Compute {
                dst,
                op: Op::Fma,
                ty,
                args,
            } = &i.kind
            {
                if *ty != Ty::F32
                    || kernel.registers.get(dst) != Some(&Ty::F32)
                    || args.len() != 3
                    || args.iter().any(|a| match a {
                        Value::Reg(n) => kernel.registers.get(n) != Some(&Ty::F32),
                        Value::Bits(Ty::F32, b) => *b > u32::MAX as u64,
                        _ => true,
                    })
                {
                    return Err(Error {
                        line: i.line,
                        unsupported: true,
                        message: "invalid F32 FMA IR",
                    });
                }
            }
        }
        kernel.validate_block_barriers()?;
        kernel.shared_access_roots()?;
    }
    let mut w = Writer {
        next: 17,
        types: vec![],
        imports: vec![],
        opencl: None,
        globals: vec![],
        annotations: vec![],
        body: vec![],
        constants: BTreeMap::new(),
        builtins: BTreeMap::new(),
        registers: BTreeMap::new(),
        module_globals: BTreeMap::new(),
        signatures: BTreeMap::new(),
        current_builtins: BTreeSet::new(),
        shared_pointer: 0,
        shared_objects: Vec::new(),
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
    if kernels.iter().any(|k| !k.shared.is_empty()) {
        w.shared_pointer = w.id();
        inst(&mut w.types, 32, &[w.shared_pointer, 4, 3]); // Workgroup -> U32
    }
    for global in first.globals.iter() {
        let stored = match global.storage {
            GlobalStorage::MutableU32 { initializer } => Some((Ty::U32, initializer as u64)),
            GlobalStorage::MutableU64 { initializer } => Some((Ty::U64, initializer)),
            GlobalStorage::Unsupported => None,
        };
        if let Some((ty, initializer)) = stored {
            let constant = w.constant(ty, initializer);
            let id = w.id();
            inst(&mut w.globals, 59, &[global_pointer(ty), id, 5, constant]);
            let mut linkage = vec![id, 41];
            linkage.extend(string_words(&global.name));
            linkage.push(0); // LinkageType Export
            inst(&mut w.annotations, 71, &linkage);
            // Linkage alone does not preserve globals unused by kernels on Intel.
            // Level Zero's host-access extension makes each exported name observable.
            let mut host_access = vec![id, 6188, 3]; // HostAccessINTEL, ReadWriteINTEL
            host_access.extend(string_words(&global.name));
            inst(&mut w.annotations, 71, &host_access);
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
        inst(&mut out, 17, &[6187]); // GlobalVariableHostAccessINTEL
        inst(
            &mut out,
            10,
            &string_words("SPV_INTEL_global_variable_host_access"),
        );
    }
    out.extend(w.imports);
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
    w.shared_objects.clear();
    for s in &k.shared {
        let length = w.constant(Ty::U32, (s.bytes / 4) as u64);
        let array = w.id();
        inst(&mut w.types, 28, &[array, 3, length]);
        let pointer = w.id();
        inst(&mut w.types, 32, &[pointer, 4, array]);
        let object = w.id();
        inst(&mut w.globals, 59, &[pointer, object, 4]);
        inst(&mut w.annotations, 71, &[object, 44, s.alignment]);
        w.shared_objects.push(object);
    }
    let roots = k
        .shared_access_roots()
        .expect("validated before generating module");
    let mut roots = roots.into_iter();
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
            let root = roots.next().unwrap();
            match &instruction.kind {
                InstructionKind::SharedLoad {
                    ty,
                    dst,
                    address,
                    offset,
                    volatile,
                } => {
                    let ptr = shared_address(w, k, address, *offset, root.unwrap());
                    let loaded = w.result(61, 3, &[ptr, if *volatile { 3 } else { 2 }, 4]);
                    let value = if *ty == Ty::F32 {
                        w.result(124, 5, &[loaded])
                    } else {
                        loaded
                    };
                    inst(&mut w.body, 62, &[w.registers[dst], value]);
                }
                InstructionKind::SharedStore {
                    ty,
                    address,
                    offset,
                    value,
                    volatile,
                } => {
                    let ptr = shared_address(w, k, address, *offset, root.unwrap());
                    let value = w.read(value, *ty);
                    let bits = if *ty == Ty::F32 {
                        w.result(124, 3, &[value])
                    } else {
                        value
                    };
                    inst(
                        &mut w.body,
                        62,
                        &[ptr, bits, if *volatile { 3 } else { 2 }, 4],
                    );
                }
                InstructionKind::BlockBarrier => {
                    // Kernel/OpenCL1.2: CTA rendezvous and visibility for shared
                    // and global accesses. Workgroup scope, SC memory ordering.
                    let scope = w.constant(Ty::U32, 2);
                    let semantics = w.constant(Ty::U32, 0x10 | 0x100 | 0x200);
                    inst(&mut w.body, 224, &[scope, scope, semantics]);
                }
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
                    let id = if *ty == Ty::U32 && k.registers[dst] == Ty::U64 {
                        w.result(113, type_id(Ty::U64), &[id]) // OpUConvert: zero extend
                    } else {
                        id
                    };
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
                    let wide = *ty == Ty::U32
                        && matches!(value, Value::Reg(r) if k.registers[r] == Ty::U64);
                    let id = w.read(value, if wide { Ty::U64 } else { *ty });
                    let id = if wide {
                        w.result(113, type_id(Ty::U32), &[id]) // OpUConvert: low 32 bits
                    } else {
                        id
                    };
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

fn shared_address(w: &mut Writer, k: &Kernel, address: &Value, offset: u64, root: usize) -> u32 {
    let ty = match address {
        Value::Reg(n) => k.registers[n],
        _ => Ty::U64,
    };
    let mut bytes = w.read(address, ty);
    if offset != 0 {
        let off = w.constant(ty, offset);
        bytes = w.result(128, type_id(ty), &[bytes, off]);
    }
    let two = w.constant(ty, 2);
    let index = w.result(194, type_id(ty), &[bytes, two]);
    w.result(65, w.shared_pointer, &[w.shared_objects[root], index])
}

#[cfg(test)]
mod global_tests {
    use super::*;
    #[test]
    fn fma_types_and_arity_are_rechecked_for_public_ir() {
        let source=".version 8.0 .target sm_52 .address_size 64 .entry f(){.reg .f32 %f<4>;mov.f32 %f0,0f3f800000;fma.rn.f32 %f1,%f0,%f0,%f0;ret;}";
        let k = ct_ptx::parse(source).unwrap();
        for change in 0..3 {
            let mut bad = k.clone();
            if let InstructionKind::Compute { ty, args, .. } =
                &mut bad.blocks[0].instructions[1].kind
            {
                match change {
                    0 => *ty = Ty::U32,
                    1 => {
                        args.pop();
                    }
                    _ => args[0] = Value::Bits(Ty::U32, 0),
                }
            }
            assert!(generate(&bad).unwrap_err().unsupported);
        }
    }
    #[test]
    fn mutated_branch_uniformity_is_rechecked_before_emission() {
        let source=".version 8.0 .target sm_52 .address_size 64 .entry sync(){.reg .pred %p; .reg .b32 %r; mov.u32 %r,%ntid.x;setp.eq.u32 %p,%r,0;@%p bra.uni END;bar.sync 0;END:ret;}";
        let mut k = ct_ptx::parse(source).unwrap();
        if let InstructionKind::Compute { args, .. } = &mut k.blocks[0].instructions[0].kind {
            args[0] = Value::Builtin(27, 0);
        }
        assert!(generate(&k).unwrap_err().unsupported);
    }
    #[test]
    fn shared_proof_is_rechecked_for_mutated_public_ir() {
        let source=".version 8.0 .target sm_52 .address_size 64 .entry sync(){.reg .b32 %r; .shared .align 4 .b8 tile[512]; mov.u32 %r,tile; st.shared.u32 [%r],7; ret;}";
        let k = ct_ptx::parse(source).unwrap();
        let mut bad = k.clone();
        bad.shared[0].bytes = 16388;
        assert!(generate(&bad).unwrap_err().unsupported);
        let mut bad = k.clone();
        bad.shared.clear();
        assert!(generate(&bad).unwrap_err().unsupported);
        let mut bad = k.clone();
        if let InstructionKind::Compute { args, .. } = &mut bad.blocks[0].instructions[0].kind {
            args[0] = Value::Bits(Ty::U32, 0);
        }
        assert!(generate(&bad).unwrap_err().unsupported);
        let mut bad = k;
        bad.blocks[0].instructions[1].kind = InstructionKind::Store {
            ty: Ty::U32,
            address: Value::Reg("%r".into()),
            offset: 0,
            value: Value::Bits(Ty::U32, 7),
            volatile: false,
        };
        assert!(generate(&bad).unwrap_err().unsupported);
    }
    #[test]
    fn mutated_truncated_shift_count_cannot_forge_shared_alignment() {
        let source=".version 8.0 .target sm_52 .address_size 64 .entry sync(){.reg .b32 %r<8>; .reg .b64 %rd; .shared .align 4 .b8 tile[512]; mov.u64 %rd,4294967296; cvt.u32.u64 %r0,%rd; mov.u32 %r1,%tid.x; shl.b32 %r2,%r1,2; mov.u32 %r3,tile; add.u32 %r4,%r3,%r2; ld.shared.u32 %r5,[%r4];ret;}";
        let mut k = ct_ptx::parse(source).unwrap();
        if let InstructionKind::Compute { args, .. } = &mut k.blocks[0].instructions[3].kind {
            args[1] = Value::Reg("%r0".into());
        }
        assert!(generate(&k).unwrap_err().unsupported);
    }
    #[test]
    fn rejects_invalid_barrier_cfg_even_for_mutated_public_ir() {
        let mut k = ct_ptx::parse(
            ".version 8.0 .target sm_52 .address_size 64 .entry sync(){bar.sync 0;ret;}",
        )
        .unwrap();
        k.blocks.push(k.blocks[0].clone());
        k.blocks[0].terminator = Terminator::Jump(2);
        assert!(generate_module(&[k]).unwrap_err().unsupported);
    }
    #[test]
    fn rejects_inconsistent_module_global_tables() {
        let source = ".version 8.0\n.target sm_52\n.address_size 64\n.global .align 4 .u32 g=7; .entry first() { ret; } .entry second() { ret; }";
        let mut m = ct_ptx::parse_module(source).unwrap();
        m.kernels[1].globals = Arc::from([]);
        assert!(generate_module(&m.kernels).unwrap_err().unsupported);
    }
}
