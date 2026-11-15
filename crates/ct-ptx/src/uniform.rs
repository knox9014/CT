//! Whole-CTA control proof. A .uni spelling is never accepted as evidence.
use crate::*;
fn reject(line: usize) -> Error {
    Error {
        line,
        unsupported: true,
        message: "unproved CTA-uniform control flow",
    }
}
pub(crate) fn edges(k: &Kernel) -> Result<Vec<Vec<usize>>, Error> {
    if k.blocks.is_empty()
        || k.blocks.len() > 128
        || k.registers.len() > 256
        || k.blocks.iter().map(|b| b.instructions.len()).sum::<usize>() > 4096
    {
        return Err(reject(1));
    }
    let mut edges = Vec::new();
    for b in &k.blocks {
        let next = match &b.terminator {
            Terminator::Return => vec![],
            Terminator::Jump(t) => vec![*t],
            Terminator::Branch {
                predicate,
                target,
                otherwise,
                ..
            } => {
                if k.registers.get(predicate) != Some(&Ty::Pred) {
                    return Err(reject(b.line));
                }
                vec![*target, *otherwise]
            }
        };
        if next.iter().any(|t| *t >= k.blocks.len()) {
            return Err(reject(b.line));
        }
        edges.push(next);
    }
    let mut can_return: Vec<bool> = k
        .blocks
        .iter()
        .map(|b| matches!(b.terminator, Terminator::Return))
        .collect();
    loop {
        let mut changed = false;
        for b in 0..edges.len() {
            if !can_return[b] && edges[b].iter().any(|t| can_return[*t]) {
                can_return[b] = true;
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }
    if can_return.iter().any(|v| !*v) {
        return Err(reject(1));
    }
    Ok(edges)
}
pub(crate) fn validate(k: &Kernel) -> Result<(), Error> {
    validate_limited(k, 4096, 65536)
}
fn validate_limited(k: &Kernel, visit_limit: usize, work_limit: usize) -> Result<(), Error> {
    let edges = edges(k)?;
    crate::parser::validate_flow(k)?;
    let mut predecessors = vec![Vec::new(); k.blocks.len()];
    for (b, next) in edges.iter().enumerate() {
        for &t in next {
            predecessors[t].push(b);
        }
    }
    let regs: BTreeMap<&str, usize> = k
        .registers
        .keys()
        .enumerate()
        .map(|(i, n)| (n.as_str(), i))
        .collect();
    let mut outputs = vec![vec![true; regs.len()]; k.blocks.len()];
    let mut inputs = outputs.clone();
    let mut visits = 0;
    let mut work = 0;
    loop {
        let mut changed = false;
        for (b, block) in k.blocks.iter().enumerate() {
            visits += 1;
            if visits > visit_limit {
                return Err(reject(block.line));
            }
            let mut state = vec![b != 0; regs.len()];
            if b != 0 {
                for &p in &predecessors[b] {
                    for (v, previous) in state.iter_mut().zip(&outputs[p]) {
                        *v &= *previous;
                    }
                }
            }
            inputs[b] = state.clone();
            for i in &block.instructions {
                work += 1;
                if work > work_limit {
                    return Err(reject(i.line));
                }
                transfer(k, i, &regs, &mut state)?;
            }
            if outputs[b] != state {
                outputs[b] = state;
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }
    // Decisions are checked only after all backedges and joins have converged.
    for (b, block) in k.blocks.iter().enumerate() {
        let mut state = inputs[b].clone();
        for i in &block.instructions {
            work += 1;
            if work > work_limit {
                return Err(reject(i.line));
            }
            transfer(k, i, &regs, &mut state)?;
        }
        if let Terminator::Branch { predicate, .. } = &block.terminator {
            if !state[regs[predicate.as_str()]] {
                return Err(reject(block.line));
            }
        }
    }
    Ok(())
}
fn transfer(
    k: &Kernel,
    i: &Instruction,
    regs: &BTreeMap<&str, usize>,
    state: &mut [bool],
) -> Result<(), Error> {
    let result = match &i.kind {
        InstructionKind::Param { dst, index } => {
            if *index >= k.params.len() {
                return Err(reject(i.line));
            }
            Some((dst, true))
        }
        InstructionKind::Load { dst, .. } | InstructionKind::SharedLoad { dst, .. } => {
            Some((dst, false))
        }
        InstructionKind::Compute { dst, args, .. } => {
            let mut uniform = true;
            for a in args {
                uniform &= match a {
                    Value::Reg(n) => state[*regs.get(n.as_str()).ok_or_else(|| reject(i.line))?],
                    Value::Builtin(kind, axis) => {
                        if !matches!(kind, 24..=27) || *axis > 2 {
                            return Err(reject(i.line));
                        }
                        *kind != 27
                    }
                    Value::Shared(n) => {
                        if !k.shared.iter().any(|s| s.name == *n) {
                            return Err(reject(i.line));
                        }
                        true
                    }
                    Value::Global(_) | Value::Bits(..) => true,
                };
            }
            Some((dst, uniform))
        }
        _ => None,
    };
    if let Some((dst, uniform)) = result {
        state[*regs.get(dst.as_str()).ok_or_else(|| reject(i.line))?] = uniform;
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn unfinished_uniform_proof_rejects_budget_exhaustion() {
        let k = crate::parse(
            ".version 8.0 .target sm_52 .address_size 64 .entry simple(){bar.sync 0;ret;}",
        )
        .unwrap();
        assert!(validate_limited(&k, 0, 65536).is_err());
        assert!(validate_limited(&k, 4096, 0).is_err());
        assert!(validate_limited(&k, 4096, 1).is_err());
    }
}
