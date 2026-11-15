//! Bounded CFG proof for relative shared addresses. Not a bounds sandbox.
use crate::*;
#[derive(Clone, Copy, PartialEq, Eq)]
enum Origin {
    Scalar,
    Other,
    Shared(usize),
}
#[derive(Clone, Copy, PartialEq, Eq)]
struct Fact {
    origin: Origin,
    residues: u8,
    known: Option<u64>,
    may_shared: bool,
}
impl Fact {
    fn join(self, other: Self) -> Self {
        Self {
            origin: if self.origin == other.origin {
                self.origin
            } else {
                Origin::Other
            },
            residues: self.residues | other.residues,
            known: if self.known == other.known {
                self.known
            } else {
                None
            },
            may_shared: self.may_shared || other.may_shared,
        }
    }
}
fn reject(line: usize) -> Error {
    Error {
        line,
        unsupported: true,
        message: "unproved static shared address/storage",
    }
}
fn combine(a: u8, b: u8, f: impl Fn(u8, u8) -> u8) -> u8 {
    let mut r = 0;
    for x in 0..4 {
        for y in 0..4 {
            if a & (1 << x) != 0 && b & (1 << y) != 0 {
                r |= 1 << (f(x, y) & 3);
            }
        }
    }
    r
}
fn read(k: &Kernel, v: &Value, state: &BTreeMap<String, Fact>, line: usize) -> Result<Fact, Error> {
    Ok(match v {
        Value::Reg(n) => *state.get(n).ok_or_else(|| reject(line))?,
        Value::Shared(n) => Fact {
            origin: Origin::Shared(
                k.shared
                    .iter()
                    .position(|s| s.name == *n)
                    .ok_or_else(|| reject(line))?,
            ),
            residues: 1,
            known: Some(0),
            may_shared: true,
        },
        Value::Global(_) => Fact {
            origin: Origin::Other,
            residues: 15,
            known: None,
            may_shared: false,
        },
        Value::Bits(_, v) => Fact {
            origin: Origin::Scalar,
            residues: 1 << (v & 3),
            known: Some(*v),
            may_shared: false,
        },
        Value::Builtin(..) => Fact {
            origin: Origin::Scalar,
            residues: 15,
            known: None,
            may_shared: false,
        },
    })
}
pub(crate) fn validate(k: &Kernel) -> Result<Vec<Option<usize>>, Error> {
    validate_limited(k, 4096, 65536)
}
fn validate_limited(
    k: &Kernel,
    visit_limit: usize,
    work_limit: usize,
) -> Result<Vec<Option<usize>>, Error> {
    let count = k.blocks.iter().map(|b| b.instructions.len()).sum();
    let has_shared_ir = k
        .blocks
        .iter()
        .flat_map(|b| &b.instructions)
        .any(|i| match &i.kind {
            InstructionKind::SharedLoad { .. } | InstructionKind::SharedStore { .. } => true,
            InstructionKind::Compute { args, op, .. } => {
                *op == Op::CvtaShared || args.iter().any(|v| matches!(v, Value::Shared(_)))
            }
            InstructionKind::Load { address, .. } => matches!(address, Value::Shared(_)),
            InstructionKind::Store { address, value, .. } => {
                matches!(address, Value::Shared(_)) || matches!(value, Value::Shared(_))
            }
            _ => false,
        });
    if k.shared.is_empty() && !has_shared_ir {
        return Ok(vec![None; count]);
    }
    crate::uniform::validate(k)?;
    if k.shared.len() > 16 {
        return Err(reject(1));
    }
    let mut names = std::collections::BTreeSet::new();
    let mut bytes = 0u32;
    for s in &k.shared {
        if !names.insert(&s.name)
            || !matches!(s.alignment, 4 | 8 | 16)
            || s.bytes == 0
            || s.bytes > MAX_STATIC_SHARED_BYTES
            || s.bytes % 4 != 0
        {
            return Err(reject(1));
        }
        bytes = bytes
            .checked_add(s.bytes.next_multiple_of(s.alignment))
            .ok_or_else(|| reject(1))?;
    }
    if bytes > MAX_STATIC_SHARED_BYTES {
        return Err(reject(1));
    }
    let unknown = Fact {
        origin: Origin::Other,
        residues: 15,
        known: None,
        may_shared: false,
    };
    let initial: BTreeMap<String, Fact> =
        k.registers.keys().map(|n| (n.clone(), unknown)).collect();
    let edges = crate::uniform::edges(k)?;
    let mut incoming = vec![None; k.blocks.len()];
    incoming[0] = Some(initial);
    let mut queue = std::collections::VecDeque::from([0]);
    let mut queued = vec![false; k.blocks.len()];
    queued[0] = true;
    let mut visits = 0;
    let mut work = 0;
    while let Some(b) = queue.pop_front() {
        visits += 1;
        if visits > visit_limit {
            return Err(reject(k.blocks[b].line));
        }
        queued[b] = false;
        let mut state = incoming[b].clone().unwrap();
        for i in &k.blocks[b].instructions {
            work += 1;
            if work > work_limit {
                return Err(reject(i.line));
            }
            if step(k, i, &mut state).is_err() {
                // During analysis a failed transfer is conservative, never an
                // accepted access/root. Final checking runs after convergence.
                if let InstructionKind::Param { dst, .. }
                | InstructionKind::Compute { dst, .. }
                | InstructionKind::Load { dst, .. }
                | InstructionKind::SharedLoad { dst, .. } = &i.kind
                {
                    state.insert(
                        dst.clone(),
                        Fact {
                            may_shared: true,
                            ..unknown
                        },
                    );
                }
            }
        }
        for &next in &edges[b] {
            if next == 0 {
                continue;
            } // virtual entry input is fixed, including backedges
            let changed = if let Some(old) = &mut incoming[next] {
                let mut changed = false;
                for (n, f) in old {
                    let merged = f.join(state[n]);
                    changed |= *f != merged;
                    *f = merged;
                }
                changed
            } else {
                incoming[next] = Some(state.clone());
                true
            };
            if changed && !queued[next] {
                queue.push_back(next);
                queued[next] = true;
            }
        }
    }
    let mut roots = Vec::new();
    for (block, input) in k.blocks.iter().zip(incoming) {
        let mut state = input.ok_or_else(|| reject(block.line))?;
        for i in &block.instructions {
            work += 1;
            if work > work_limit {
                return Err(reject(i.line));
            }
            roots.push(step(k, i, &mut state)?);
        }
    }
    Ok(roots)
}
fn step(
    k: &Kernel,
    i: &Instruction,
    state: &mut BTreeMap<String, Fact>,
) -> Result<Option<usize>, Error> {
    let unknown = Fact {
        origin: Origin::Other,
        residues: 15,
        known: None,
        may_shared: false,
    };
    let scalar = Fact {
        origin: Origin::Scalar,
        ..unknown
    };
    let r = |v: &Value| read(k, v, state, i.line);
    let mut root = None;
    let assignment = match &i.kind {
        InstructionKind::BlockBarrier => None,
        InstructionKind::Param { dst, index } => Some((
            dst,
            if k.params.get(*index).ok_or_else(|| reject(i.line))?.kind == ParamKind::Pointer {
                unknown
            } else {
                scalar
            },
        )),
        InstructionKind::Compute { dst, op, ty, args } => {
            let f: Vec<_> = args.iter().map(r).collect::<Result<_, _>>()?;
            let shared = f.iter().any(|v| v.may_shared);
            let result = if shared {
                if !matches!(ty, Ty::U32 | Ty::U64) {
                    return Err(reject(i.line));
                }
                match op {
                    Op::Mov if f.len() == 1 => f[0],
                    Op::CvtaShared if f.len() == 1 && *ty == Ty::U64 => f[0],
                    Op::Convert {
                        to: Ty::U64,
                        signed: false,
                    } if f.len() == 1 && *ty == Ty::U32 => f[0],
                    Op::Add if f.len() == 2 => {
                        let (a, b) = if matches!(f[0].origin, Origin::Shared(_)) {
                            (f[0], f[1])
                        } else {
                            (f[1], f[0])
                        };
                        if b.origin != Origin::Scalar {
                            return Err(reject(i.line));
                        }
                        Fact {
                            origin: a.origin,
                            may_shared: true,
                            residues: combine(a.residues, b.residues, u8::wrapping_add),
                            known: a.known.zip(b.known).map(|(x, y)| {
                                if *ty == Ty::U32 {
                                    x.wrapping_add(y) & 0xffff_ffff
                                } else {
                                    x.wrapping_add(y)
                                }
                            }),
                        }
                    }
                    _ => return Err(reject(i.line)),
                }
            } else {
                if *op == Op::CvtaShared {
                    return Err(reject(i.line));
                }
                if f.iter().any(|f| f.origin != Origin::Scalar) {
                    unknown
                } else if *op == Op::Mov && f.len() == 1 {
                    f[0]
                } else if matches!(op, Op::Convert { .. }) && f.len() == 1 {
                    // Low two bits survive integer width changes. The full
                    // source constant may truncate or sign-extend, so it
                    // cannot be used as the converted shift count.
                    Fact {
                        known: None,
                        ..f[0]
                    }
                } else {
                    let residues = match op {
                        Op::Add if f.len() == 2 => {
                            combine(f[0].residues, f[1].residues, u8::wrapping_add)
                        }
                        Op::Mul | Op::MulWide | Op::SignedMulWide if f.len() == 2 => {
                            combine(f[0].residues, f[1].residues, u8::wrapping_mul)
                        }
                        Op::And if f.len() == 2 => {
                            combine(f[0].residues, f[1].residues, |a, b| a & b)
                        }
                        Op::Shl if f.len() == 2 => match f[1].known {
                            Some(v) if v >= 2 => 1,
                            Some(v) => combine(f[0].residues, 1, |a, _| a << (v as u32)),
                            None => 15,
                        },
                        _ => 15,
                    };
                    Fact { residues, ..scalar }
                }
            };
            Some((dst, result))
        }
        InstructionKind::Load { dst, address, .. } => {
            if r(address)?.may_shared {
                return Err(reject(i.line));
            }
            Some((dst, scalar))
        }
        InstructionKind::Store { address, value, .. } => {
            if [r(address)?, r(value)?].iter().any(|v| v.may_shared) {
                return Err(reject(i.line));
            }
            None
        }
        InstructionKind::SharedLoad {
            ty,
            dst,
            address,
            offset,
            ..
        } => {
            root = Some(access(k, address, *offset, *ty, state, i.line)?);
            if k.registers.get(dst) != Some(ty) {
                return Err(reject(i.line));
            }
            Some((dst, scalar))
        }
        InstructionKind::SharedStore {
            ty,
            address,
            offset,
            value,
            ..
        } => {
            root = Some(access(k, address, *offset, *ty, state, i.line)?);
            if r(value)?.may_shared {
                return Err(reject(i.line));
            }
            match value {
                Value::Reg(n) if k.registers.get(n) == Some(ty) => {}
                Value::Bits(t, _) if t == ty => {}
                _ => return Err(reject(i.line)),
            };
            None
        }
    };
    if let Some((dst, f)) = assignment {
        if !state.contains_key(dst) {
            return Err(reject(i.line));
        }
        state.insert(dst.clone(), f);
    }
    Ok(root)
}

fn access(
    k: &Kernel,
    address: &Value,
    offset: u64,
    ty: Ty,
    state: &BTreeMap<String, Fact>,
    line: usize,
) -> Result<usize, Error> {
    if !matches!(ty, Ty::U32 | Ty::F32) || !offset.is_multiple_of(4) {
        return Err(reject(line));
    }
    let f = read(k, address, state, line)?;
    let Origin::Shared(index) = f.origin else {
        return Err(reject(line));
    };
    if f.residues != 1 {
        return Err(reject(line));
    }
    let width = match address {
        Value::Reg(n) => *k.registers.get(n).ok_or_else(|| reject(line))?,
        Value::Shared(_) => Ty::U64,
        _ => return Err(reject(line)),
    };
    if !matches!(width, Ty::U32 | Ty::U64) || (width == Ty::U32 && offset > u32::MAX as u64) {
        return Err(reject(line));
    }
    if let Some(base) = f.known {
        let sum = if width == Ty::U32 {
            base.wrapping_add(offset) & 0xffff_ffff
        } else {
            base.wrapping_add(offset)
        };
        if sum >= k.shared[index].bytes as u64 {
            return Err(reject(line));
        }
    }
    Ok(index)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn unfinished_shared_cfg_proof_rejects_budget_exhaustion() {
        let k=crate::parse(".version 8.0 .target sm_52 .address_size 64 .entry simple(){.reg .b32 %r; .shared .align 4 .b8 a[512]; bra NEXT;NEXT:ld.shared.u32 %r,[a];ret;}").unwrap();
        assert!(validate_limited(&k, 0, 65536).is_err());
        assert!(validate_limited(&k, 4096, 0).is_err());
    }
}
