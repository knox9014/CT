//! Bounded alignment proof, not a bounds or ownership proof for derived addresses.
use crate::*;
use std::collections::VecDeque;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Origin {
    Scalar,
    Param(usize),
    Unknown,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Fact {
    origin: Origin,
    residues: u8,
}
impl Fact {
    fn unknown() -> Self {
        Self {
            origin: Origin::Unknown,
            residues: 255,
        }
    }
    fn scalar(residues: u8) -> Self {
        Self {
            origin: Origin::Scalar,
            residues,
        }
    }
    fn join(self, other: Self) -> Self {
        Self {
            origin: if self.origin == other.origin {
                self.origin
            } else {
                Origin::Unknown
            },
            residues: self.residues | other.residues,
        }
    }
}

type Registers<'a> = BTreeMap<&'a str, usize>;
fn read(value: &Value, state: &[Fact], regs: &Registers<'_>) -> Fact {
    match value {
        Value::Reg(r) => state[regs[r.as_str()]],
        Value::Bits(_, bits) => Fact::scalar(1 << (bits & 7)),
        Value::Builtin(..) => Fact::scalar(255),
        Value::Global(_) | Value::Shared(_) => Fact::unknown(),
    }
}
fn residues(a: u8, b: u8, operation: impl Fn(u8, u8) -> u8) -> u8 {
    let mut out = 0;
    for x in 0..8 {
        for y in 0..8 {
            if a & (1 << x) != 0 && b & (1 << y) != 0 {
                out |= 1 << (operation(x, y) & 7);
            }
        }
    }
    out
}
fn compute(op: Op, ty: Ty, args: &[Value], state: &[Fact], regs: &Registers<'_>) -> Fact {
    let facts: Vec<_> = args.iter().map(|a| read(a, state, regs)).collect();
    if ty == Ty::F32 || ty == Ty::Pred {
        return Fact::unknown();
    }
    match op {
        Op::Mov | Op::Cvta | Op::CvtaShared => return facts[0],
        Op::Convert { to: Ty::U64, .. } if ty == Ty::U64 => return facts[0],
        Op::Select => return facts[0].join(facts[1]),
        _ => {}
    }
    if matches!(op, Op::Add | Op::Sub) {
        let origin = match (facts[0].origin, facts[1].origin, op) {
            (Origin::Param(i), Origin::Scalar, _) => Origin::Param(i),
            (Origin::Scalar, Origin::Param(i), Op::Add) => Origin::Param(i),
            (Origin::Scalar, Origin::Scalar, _) => Origin::Scalar,
            _ => return Fact::unknown(),
        };
        return Fact {
            origin,
            residues: residues(facts[0].residues, facts[1].residues, |a, b| {
                if op == Op::Add {
                    a.wrapping_add(b)
                } else {
                    a.wrapping_sub(b)
                }
            }),
        };
    }
    // Unsupported operations on pointer-derived data never regain Scalar status.
    if facts.iter().any(|f| f.origin != Origin::Scalar) {
        return Fact::unknown();
    }
    let r = match op {
        Op::Convert { .. } => facts[0].residues,
        Op::Mul | Op::MulWide | Op::SignedMulWide => {
            residues(facts[0].residues, facts[1].residues, |a, b| {
                a.wrapping_mul(b)
            })
        }
        Op::Mad => residues(
            residues(facts[0].residues, facts[1].residues, |a, b| {
                a.wrapping_mul(b)
            }),
            facts[2].residues,
            |a, b| a.wrapping_add(b),
        ),
        Op::And => residues(facts[0].residues, facts[1].residues, |a, b| a & b),
        Op::Or => residues(facts[0].residues, facts[1].residues, |a, b| a | b),
        Op::Xor => residues(facts[0].residues, facts[1].residues, |a, b| a ^ b),
        Op::Shl => match args[1] {
            Value::Bits(_, count) if count >= 3 => 1,
            Value::Bits(_, count) => residues(facts[0].residues, 1, |a, _| a << count),
            _ => 255,
        },
        _ => 255,
    };
    Fact::scalar(r)
}

fn transfer(
    k: &Kernel,
    inferred: &[usize],
    regs: &Registers<'_>,
    state: &mut [Fact],
    i: &Instruction,
) {
    let (dst, fact) = match &i.kind {
        InstructionKind::Param { dst, index } => {
            let p = &k.params[*index];
            let fact = if p.kind == ParamKind::Pointer {
                Fact {
                    origin: Origin::Param(*index),
                    residues: if p.alignment == 8 || inferred.contains(index) {
                        1
                    } else {
                        17
                    },
                }
            } else {
                Fact::scalar(255)
            };
            (dst, fact)
        }
        InstructionKind::Compute { dst, op, ty, args } => {
            (dst, compute(*op, *ty, args, state, regs))
        }
        InstructionKind::Load { dst, .. } | InstructionKind::SharedLoad { dst, .. } => {
            (dst, Fact::scalar(255))
        }
        InstructionKind::Store { .. }
        | InstructionKind::SharedStore { .. }
        | InstructionKind::BlockBarrier => return,
    };
    state[regs[dst.as_str()]] = fact;
}

fn unsupported(line: usize) -> Error {
    Error {
        line,
        unsupported: true,
        message: "unproved U64 address alignment/origin",
    }
}

pub(crate) fn validate(k: &mut Kernel, inferred: &[usize]) -> Result<(), Error> {
    validate_limited(k, inferred, 4096)
}

fn validate_limited(k: &mut Kernel, inferred: &[usize], budget: usize) -> Result<(), Error> {
    if !k.blocks.iter().flat_map(|b| &b.instructions).any(|i| matches!(
        &i.kind, InstructionKind::Load {ty: Ty::U64, address, ..}
            | InstructionKind::Store {ty: Ty::U64, address, ..} if !matches!(address, Value::Global(_))
    )) { return Ok(()); }
    let regs: Registers<'_> = k
        .registers
        .keys()
        .enumerate()
        .map(|(i, r)| (r.as_str(), i))
        .collect();
    let mut incoming: Vec<Option<Vec<Fact>>> = vec![None; k.blocks.len()];
    // A virtual entry edge remains unknown even if the program branches to block0.
    incoming[0] = Some(vec![Fact::unknown(); regs.len()]);
    let mut queue = VecDeque::from([0]);
    let mut queued = vec![false; k.blocks.len()];
    queued[0] = true;
    let mut visits = 0;
    while let Some(block) = queue.pop_front() {
        visits += 1;
        if visits > budget {
            return Err(unsupported(k.blocks[block].line));
        }
        queued[block] = false;
        let mut out = incoming[block].clone().unwrap();
        for i in &k.blocks[block].instructions {
            transfer(k, inferred, &regs, &mut out, i);
        }
        let successors = match k.blocks[block].terminator {
            Terminator::Return => vec![],
            Terminator::Jump(t) => vec![t],
            Terminator::Branch {
                target, otherwise, ..
            } => vec![target, otherwise],
        };
        for next in successors {
            let changed = if let Some(old) = &mut incoming[next] {
                let mut changed = false;
                for (a, b) in old.iter_mut().zip(&out) {
                    let merged = a.join(*b);
                    changed |= merged != *a;
                    *a = merged;
                }
                changed
            } else {
                incoming[next] = Some(out.clone());
                true
            };
            if changed && !queued[next] {
                queue.push_back(next);
                queued[next] = true;
            }
        }
    }
    let mut required = vec![false; k.params.len()];
    for (b, input) in k.blocks.iter().zip(incoming) {
        let mut state = input.ok_or_else(|| unsupported(b.line))?;
        for i in &b.instructions {
            if let InstructionKind::Load {
                ty: Ty::U64,
                address,
                offset,
                ..
            }
            | InstructionKind::Store {
                ty: Ty::U64,
                address,
                offset,
                ..
            } = &i.kind
            {
                if !matches!(address, Value::Global(_)) {
                    let f = read(address, &state, &regs);
                    let Origin::Param(root) = f.origin else {
                        return Err(unsupported(i.line));
                    };
                    if residues(f.residues, 1 << (offset & 7), |a, b| a.wrapping_add(b)) != 1 {
                        return Err(unsupported(i.line));
                    }
                    required[root] = true;
                }
            }
            transfer(k, inferred, &regs, &mut state, i);
        }
    }
    for (index, needed) in required.into_iter().enumerate() {
        if needed && inferred.contains(&index) {
            k.params[index].alignment = 8;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unfinished_fixed_point_never_passes_at_budget_exhaustion() {
        let mut k = crate::parse(".version 8.0 .target sm_52 .address_size 64 .entry looped(.param .u64 .ptr .global .align 8 p) { .reg .b64 %a; .reg .pred %p; ld.param.u64 %a,[p]; setp.eq.u64 %p,%a,0; LOOP: st.global.u64 [%a],1; add.u64 %a,%a,8; @%p bra LOOP; ret; }").unwrap();
        assert!(validate_limited(&mut k, &[], 1).unwrap_err().unsupported);
        validate_limited(&mut k, &[], 4096).unwrap();
    }
}
