use crate::*;
use std::collections::{BTreeSet, VecDeque};

#[derive(Clone)]
struct Token {
    text: String,
    line: usize,
}
fn fail(line: usize, message: &'static str) -> Error {
    Error {
        line,
        unsupported: false,
        message,
    }
}
fn unsupported(line: usize) -> Error {
    Error {
        line,
        unsupported: true,
        message: "outside the implemented PTX profile",
    }
}
fn lex(source: &str) -> Result<Vec<Token>, Error> {
    if source.len() > 262144 {
        return Err(unsupported(1));
    }
    let b = source.as_bytes();
    let (mut i, mut line) = (0, 1);
    let mut out = Vec::new();
    while i < b.len() {
        if b[i].is_ascii_whitespace() {
            if b[i] == b'\n' {
                line += 1;
            }
            i += 1;
            continue;
        }
        if b[i..].starts_with(b"//") {
            while i < b.len() && b[i] != b'\n' {
                i += 1;
            }
            continue;
        }
        if b[i..].starts_with(b"/*") {
            i += 2;
            while i < b.len() && !b[i..].starts_with(b"*/") {
                if b[i] == b'\n' {
                    line += 1;
                }
                i += 1;
            }
            if i == b.len() {
                return Err(fail(line, "unterminated comment"));
            }
            i += 2;
            continue;
        }
        let start = i;
        if b";:,{}[]()<>@!+-=".contains(&b[i]) {
            i += 1;
        } else {
            while i < b.len() && (b[i].is_ascii_alphanumeric() || b"._%$".contains(&b[i])) {
                i += 1;
            }
            if i == start {
                return Err(unsupported(line));
            }
        }
        out.push(Token {
            text: source[start..i].into(),
            line,
        });
        if out.len() > 65536 {
            return Err(unsupported(line));
        }
    }
    Ok(out)
}
struct Parser {
    tokens: Vec<Token>,
    pos: usize,
}
impl Parser {
    fn line(&self) -> usize {
        self.tokens
            .get(self.pos)
            .or_else(|| self.tokens.last())
            .map_or(1, |t| t.line)
    }
    fn peek(&self) -> &str {
        self.tokens.get(self.pos).map_or("", |t| t.text.as_str())
    }
    fn take(&mut self) -> Result<String, Error> {
        let t = self
            .tokens
            .get(self.pos)
            .ok_or_else(|| fail(self.line(), "unexpected end"))?
            .text
            .clone();
        self.pos += 1;
        Ok(t)
    }
    fn eat(&mut self, s: &str) -> bool {
        if self.peek() == s {
            self.pos += 1;
            true
        } else {
            false
        }
    }
    fn expect(&mut self, s: &str) -> Result<(), Error> {
        if self.eat(s) {
            Ok(())
        } else {
            Err(fail(self.line(), "unexpected syntax"))
        }
    }
}
fn identifier(s: &str) -> bool {
    !s.is_empty()
        && s.len() <= 128
        && (s.as_bytes()[0].is_ascii_alphabetic()
            || (s.len() > 1 && b"_$".contains(&s.as_bytes()[0])))
        && s.bytes().enumerate().all(|(i, b)| {
            b.is_ascii_alphabetic() || b"_$".contains(&b) || (i > 0 && b.is_ascii_digit())
        })
}
fn ty(s: &str) -> Option<Ty> {
    match s {
        ".pred" => Some(Ty::Pred),
        ".u32" | ".b32" => Some(Ty::U32),
        ".u64" | ".b64" => Some(Ty::U64),
        ".f32" => Some(Ty::F32),
        _ => None,
    }
}
fn number(s: &str) -> Option<u64> {
    if let Some(v) = s.strip_prefix("0x") {
        u64::from_str_radix(v, 16).ok()
    } else if s.len() > 1 && s.starts_with('0') {
        u64::from_str_radix(&s[1..], 8).ok()
    } else {
        s.parse().ok()
    }
}
fn value(
    tokens: &[String],
    expected: Ty,
    regs: &BTreeMap<String, Ty>,
    line: usize,
) -> Result<Value, Error> {
    if tokens.len() != 1 {
        return Err(fail(line, "invalid operand"));
    }
    let s = &tokens[0];
    if let Some(&actual) = regs.get(s) {
        if actual != expected {
            return Err(fail(line, "register type mismatch"));
        }
        return Ok(Value::Reg(s.clone()));
    }
    if expected == Ty::U32 {
        let builtin = match s.as_str() {
            "%nctaid.x" => Some(24),
            "%ntid.x" => Some(25),
            "%ctaid.x" => Some(26),
            "%tid.x" => Some(27),
            _ => None,
        };
        if let Some(v) = builtin {
            return Ok(Value::Builtin(v));
        }
    }
    if s.starts_with('%') {
        return Err(fail(line, "undeclared or unsupported register"));
    }
    let bits = if expected == Ty::F32 {
        s.strip_prefix("0f")
            .filter(|v| v.len() == 8)
            .and_then(|v| u32::from_str_radix(v, 16).ok())
            .map(u64::from)
    } else {
        number(s)
    }
    .ok_or_else(|| fail(line, "invalid immediate"))?;
    if expected == Ty::Pred || (expected == Ty::U32 && bits > u32::MAX as u64) {
        return Err(fail(line, "immediate out of range"));
    }
    Ok(Value::Bits(expected, bits))
}
fn destination(
    tokens: &[String],
    expected: Ty,
    regs: &BTreeMap<String, Ty>,
    line: usize,
) -> Result<String, Error> {
    if tokens.len() != 1 || regs.get(&tokens[0]) != Some(&expected) {
        return Err(fail(line, "invalid destination register/type"));
    }
    Ok(tokens[0].clone())
}
fn address(
    tokens: &[String],
    regs: &BTreeMap<String, Ty>,
    line: usize,
) -> Result<(Value, u64), Error> {
    if tokens.first().map(String::as_str) != Some("[")
        || tokens.last().map(String::as_str) != Some("]")
    {
        return Err(fail(line, "invalid address"));
    }
    let inside = &tokens[1..tokens.len() - 1];
    let offset = if inside.len() == 1 {
        0
    } else if inside.len() == 3 && inside[1] == "+" {
        number(&inside[2]).ok_or_else(|| fail(line, "invalid address offset"))?
    } else {
        return Err(unsupported(line));
    };
    if !offset.is_multiple_of(4) {
        return Err(unsupported(line));
    }
    Ok((value(&inside[..1], Ty::U64, regs, line)?, offset))
}
fn instruction(
    op: &str,
    args: &[Vec<String>],
    regs: &BTreeMap<String, Ty>,
    params: &[Param],
    line: usize,
) -> Result<Instruction, Error> {
    let err = || fail(line, "invalid instruction operands");
    let kind = if let Some(suffix) = op.strip_prefix("ld.param.") {
        if args.len() != 2 || args[1].len() != 3 || args[1][0] != "[" || args[1][2] != "]" {
            return Err(err());
        }
        let dtype = ty(&format!(".{suffix}")).ok_or_else(|| unsupported(line))?;
        let index = params
            .iter()
            .position(|p| p.name == args[1][1])
            .ok_or_else(err)?;
        let pt = match params[index].kind {
            ParamKind::Pointer => Ty::U64,
            ParamKind::U32 => Ty::U32,
            ParamKind::F32 => Ty::F32,
        };
        if pt != dtype {
            return Err(fail(line, "parameter type mismatch"));
        }
        InstructionKind::Param {
            dst: destination(&args[0], dtype, regs, line)?,
            index,
        }
    } else if op == "ld.global.f32" {
        if args.len() != 2 {
            return Err(err());
        }
        let (a, offset) = address(&args[1], regs, line)?;
        InstructionKind::Load {
            dst: destination(&args[0], Ty::F32, regs, line)?,
            address: a,
            offset,
        }
    } else if op == "st.global.f32" {
        if args.len() != 2 {
            return Err(err());
        }
        let (a, offset) = address(&args[0], regs, line)?;
        InstructionKind::Store {
            address: a,
            offset,
            value: value(&args[1], Ty::F32, regs, line)?,
        }
    } else {
        let (operation, t, n) = match op {
            "mov.u32" | "mov.b32" => (Op::Mov, Ty::U32, 1),
            "mov.u64" | "mov.b64" => (Op::Mov, Ty::U64, 1),
            "mov.f32" => (Op::Mov, Ty::F32, 1),
            "cvta.to.global.u64" => (Op::Cvta, Ty::U64, 1),
            "add.u32" => (Op::Add, Ty::U32, 2),
            "add.u64" | "add.s64" => (Op::Add, Ty::U64, 2),
            "sub.u32" => (Op::Sub, Ty::U32, 2),
            "mul.lo.u32" => (Op::Mul, Ty::U32, 2),
            "mul.wide.u32" => (Op::MulWide, Ty::U32, 2),
            "mul.wide.s32" => (Op::SignedMulWide, Ty::U32, 2),
            "mad.lo.u32" | "mad.lo.s32" => (Op::Mad, Ty::U32, 3),
            "div.u32" => (Op::Div, Ty::U32, 2),
            "rem.u32" => (Op::Rem, Ty::U32, 2),
            "add.f32" | "add.rn.f32" => (Op::Add, Ty::F32, 2),
            "mul.f32" | "mul.rn.f32" => (Op::Mul, Ty::F32, 2),
            "sub.f32" | "sub.rn.f32" => (Op::Sub, Ty::F32, 2),
            "setp.ge.u32" => (Op::Ge, Ty::U32, 2),
            "setp.ge.s32" => (Op::SignedGe, Ty::U32, 2),
            "setp.lt.s32" => (Op::SignedLt, Ty::U32, 2),
            "setp.lt.u32" => (Op::Lt, Ty::U32, 2),
            "setp.eq.u32" => (Op::Eq, Ty::U32, 2),
            "setp.eq.u64" => (Op::Eq, Ty::U64, 2),
            "setp.lt.f32" => (Op::Lt, Ty::F32, 2),
            "setp.ge.f32" => (Op::Ge, Ty::F32, 2),
            "selp.f32" => (Op::Select, Ty::F32, 3),
            _ => return Err(unsupported(line)),
        };
        if args.len() != n + 1 {
            return Err(err());
        }
        let dt = if matches!(
            operation,
            Op::Ge | Op::Lt | Op::Eq | Op::SignedGe | Op::SignedLt
        ) {
            Ty::Pred
        } else if matches!(operation, Op::MulWide | Op::SignedMulWide) {
            Ty::U64
        } else {
            t
        };
        let mut values = Vec::new();
        for (i, a) in args[1..].iter().enumerate() {
            values.push(value(
                a,
                if operation == Op::Select && i == 2 {
                    Ty::Pred
                } else {
                    t
                },
                regs,
                line,
            )?);
        }
        InstructionKind::Compute {
            dst: destination(&args[0], dt, regs, line)?,
            op: operation,
            ty: t,
            args: values,
        }
    };
    Ok(Instruction { line, kind })
}
enum PendingTerm {
    Return,
    Jump(String),
    To(usize),
    Branch(String, bool, String, usize),
}
struct PendingBlock {
    instructions: Vec<Instruction>,
    term: Option<PendingTerm>,
    line: usize,
}
fn new_block(line: usize) -> PendingBlock {
    PendingBlock {
        instructions: Vec::new(),
        term: None,
        line,
    }
}

pub fn parse(source: &str) -> Result<Kernel, Error> {
    let mut module = parse_module(source)?;
    if module.kernels.len() != 1 {
        return Err(unsupported(1));
    }
    Ok(module
        .kernels
        .pop()
        .ok_or_else(|| fail(1, "missing entry"))?)
}

pub fn parse_module(source: &str) -> Result<Module, Error> {
    let mut p = Parser {
        tokens: lex(source)?,
        pos: 0,
    };
    p.expect(".version")?;
    let version = p.take()?;
    if !matches!(version.as_str(), "7.0" | "8.0") {
        return Err(unsupported(p.line()));
    }
    p.expect(".target")?;
    let target = p.take()?;
    if !matches!(
        (version.as_str(), target.as_str()),
        ("7.0", "sm_50") | ("8.0", "sm_52")
    ) {
        return Err(unsupported(p.line()));
    }
    p.expect(".address_size")?;
    if p.take()? != "64" {
        return Err(unsupported(p.line()));
    }
    let mut globals = BTreeSet::new();
    while p.eat(".global") {
        p.expect(".align")?;
        p.expect("8")?;
        let ty = p.take()?;
        let global = p.take()?;
        if !identifier(&global) || !globals.insert(global) || globals.len() > 256 {
            return Err(fail(p.line(), "invalid/duplicate global"));
        }
        match ty.as_str() {
            ".u64" => {
                if p.eat("=") {
                    number(&p.take()?)
                        .ok_or_else(|| fail(p.line(), "invalid global initializer"))?;
                }
            }
            ".b8" => {
                p.expect("[")?;
                let size = number(&p.take()?)
                    .filter(|n| (1..=4096).contains(n))
                    .ok_or_else(|| unsupported(p.line()))?;
                p.expect("]")?;
                if p.eat("=") {
                    p.expect("{")?;
                    for i in 0..size {
                        if i > 0 {
                            p.expect(",")?;
                        }
                        number(&p.take()?)
                            .filter(|n| *n <= 255)
                            .ok_or_else(|| fail(p.line(), "invalid global initializer"))?;
                    }
                    p.expect("}")?;
                }
            }
            _ => return Err(unsupported(p.line())),
        }
        p.expect(";")?;
    }
    let profile = if version == "7.0" {
        Profile {
            major: 7,
            minor: 0,
            target: 50,
        }
    } else {
        Profile {
            major: 8,
            minor: 0,
            target: 52,
        }
    };
    let mut kernels = Vec::new();
    let mut names = BTreeSet::new();
    while p.pos < p.tokens.len() {
        if kernels.len() >= 32 {
            return Err(unsupported(p.line()));
        }
        let kernel = parse_kernel(&mut p, profile, &globals)?;
        if !names.insert(kernel.name.clone()) {
            return Err(fail(p.line(), "duplicate entry"));
        }
        kernels.push(kernel);
    }
    if kernels.is_empty() {
        return Err(fail(p.line(), "missing entry"));
    }
    Ok(Module { profile, kernels })
}

fn parse_kernel(
    p: &mut Parser,
    profile: Profile,
    globals: &BTreeSet<String>,
) -> Result<Kernel, Error> {
    if p.peek() != ".visible" {
        return Err(unsupported(p.line()));
    }
    p.expect(".visible")?;
    p.expect(".entry")?;
    let name = p.take()?;
    if !identifier(&name) || globals.contains(&name) {
        return Err(fail(p.line(), "invalid entry name"));
    }
    p.expect("(")?;
    let mut params: Vec<Param> = Vec::new();
    let mut inferred = Vec::new();
    if p.peek() != ")" {
        loop {
            p.expect(".param")?;
            let t = p.take()?;
            let kind = match t.as_str() {
                ".u32" => ParamKind::U32,
                ".f32" => ParamKind::F32,
                ".u64" => {
                    if p.eat(".ptr") {
                        p.expect(".global")?;
                        p.expect(".align")?;
                        p.expect("4")?;
                    } else {
                        inferred.push(params.len());
                    }
                    ParamKind::Pointer
                }
                _ => return Err(unsupported(p.line())),
            };
            let n = p.take()?;
            if !identifier(&n) || globals.contains(&n) || params.iter().any(|v| v.name == n) {
                return Err(fail(p.line(), "invalid/duplicate parameter"));
            }
            params.push(Param { name: n, kind });
            if params.len() > 32 {
                return Err(unsupported(p.line()));
            }
            if !p.eat(",") {
                break;
            }
        }
    }
    p.expect(")")?;
    p.expect("{")?;
    let mut regs = BTreeMap::new();
    let mut labels = BTreeMap::new();
    let mut blocks = vec![new_block(p.line())];
    let mut executable = false;
    let mut total = 0;
    while p.peek() != "}" {
        if p.peek().is_empty() {
            return Err(fail(p.line(), "missing function end"));
        }
        let line = p.line();
        let op = p.take()?;
        if op == ".reg" {
            if executable {
                return Err(unsupported(line));
            }
            let t = ty(&p.take()?).ok_or_else(|| unsupported(line))?;
            let base = p.take()?;
            if !base.starts_with('%') || !identifier(&base[1..]) {
                return Err(fail(line, "invalid register name"));
            }
            let names = if p.eat("<") {
                let n = number(&p.take()?).ok_or_else(|| fail(line, "invalid register count"))?;
                if n == 0 || n > 256 {
                    return Err(unsupported(line));
                }
                p.expect(">")?;
                (0..n).map(|i| format!("{base}{i}")).collect::<Vec<_>>()
            } else {
                vec![base]
            };
            p.expect(";")?;
            for n in names {
                if regs.insert(n, t).is_some() {
                    return Err(fail(line, "duplicate register"));
                }
            }
            if regs.len() > 256 {
                return Err(unsupported(line));
            }
            continue;
        }
        executable = true;
        if p.eat(":") {
            if blocks.len() >= 128 {
                return Err(unsupported(line));
            }
            if !identifier(&op) || labels.contains_key(&op) {
                return Err(fail(line, "invalid/duplicate label"));
            }
            let index = blocks.len();
            if blocks.last().unwrap().term.is_none() {
                blocks.last_mut().unwrap().term = Some(PendingTerm::To(index));
            }
            labels.insert(op, index);
            blocks.push(new_block(line));
            continue;
        }
        if blocks.last().unwrap().term.is_some() {
            return Err(fail(line, "instruction after terminator requires a label"));
        }
        match op.as_str() {
            "@" => {
                let neg = p.eat("!");
                let pred = p.take()?;
                if regs.get(&pred) != Some(&Ty::Pred) {
                    return Err(fail(line, "invalid branch predicate"));
                }
                p.expect("bra")?;
                let target = p.take()?;
                p.expect(";")?;
                let next = blocks.len();
                blocks.last_mut().unwrap().term =
                    Some(PendingTerm::Branch(pred, neg, target, next));
                blocks.push(new_block(line));
            }
            "bra" => {
                let target = p.take()?;
                p.expect(";")?;
                blocks.last_mut().unwrap().term = Some(PendingTerm::Jump(target));
            }
            "ret" => {
                p.expect(";")?;
                blocks.last_mut().unwrap().term = Some(PendingTerm::Return);
            }
            _ => {
                let mut args = vec![Vec::new()];
                while p.peek() != ";" {
                    let t = p.take()?;
                    if t == "," {
                        args.push(Vec::new());
                    } else {
                        args.last_mut().unwrap().push(t);
                    }
                }
                p.expect(";")?;
                blocks
                    .last_mut()
                    .unwrap()
                    .instructions
                    .push(instruction(&op, &args, &regs, &params, line)?);
                total += 1;
            }
        }
        if blocks.len() > 128 || total > 4096 {
            return Err(unsupported(line));
        }
    }
    p.expect("}")?;
    let mut final_blocks = Vec::new();
    for b in blocks {
        let target = |name: &str| {
            labels
                .get(name)
                .copied()
                .ok_or_else(|| fail(b.line, "unknown branch label"))
        };
        let term = match b
            .term
            .ok_or_else(|| fail(b.line, "block lacks terminator"))?
        {
            PendingTerm::Return => Terminator::Return,
            PendingTerm::Jump(n) => Terminator::Jump(target(&n)?),
            PendingTerm::To(i) => Terminator::Jump(i),
            PendingTerm::Branch(predicate, negated, n, otherwise) => Terminator::Branch {
                predicate,
                negated,
                target: target(&n)?,
                otherwise,
            },
        };
        final_blocks.push(Block {
            instructions: b.instructions,
            terminator: term,
            line: b.line,
        });
    }
    let kernel = Kernel {
        profile,
        name,
        params,
        registers: regs,
        blocks: final_blocks,
    };
    validate_flow(&kernel)?;
    validate_inferred_pointers(&kernel, &inferred)?;
    Ok(kernel)
}

fn validate_inferred_pointers(k: &Kernel, inferred: &[usize]) -> Result<(), Error> {
    let instructions: Vec<_> = k.blocks.iter().flat_map(|b| &b.instructions).collect();
    for index in inferred {
        let loads: Vec<_> = instructions
            .iter()
            .filter_map(|i| match &i.kind {
                InstructionKind::Param { dst, index: p } if p == index => Some(dst.as_str()),
                _ => None,
            })
            .collect();
        if loads.is_empty() {
            return Err(unsupported(1));
        }
        for register in loads {
            if instructions
                .iter()
                .filter(|i| definition(&i.kind) == Some(register))
                .count()
                != 1
            {
                return Err(unsupported(1));
            }
            let consumers: Vec<_> = instructions
                .iter()
                .filter(|i| reads(&i.kind).contains(&register))
                .collect();
            if consumers.is_empty()
                || consumers
                    .iter()
                    .any(|i| !matches!(i.kind, InstructionKind::Compute { op: Op::Cvta, .. }))
            {
                return Err(unsupported(1));
            }
        }
    }
    Ok(())
}

fn reads(i: &InstructionKind) -> Vec<&str> {
    let values: Vec<&Value> = match i {
        InstructionKind::Param { .. } => vec![],
        InstructionKind::Compute { args, .. } => args.iter().collect(),
        InstructionKind::Load { address, .. } => vec![address],
        InstructionKind::Store { address, value, .. } => vec![address, value],
    };
    values
        .into_iter()
        .filter_map(|v| {
            if let Value::Reg(n) = v {
                Some(n.as_str())
            } else {
                None
            }
        })
        .collect()
}
fn definition(i: &InstructionKind) -> Option<&str> {
    match i {
        InstructionKind::Param { dst, .. }
        | InstructionKind::Compute { dst, .. }
        | InstructionKind::Load { dst, .. } => Some(dst),
        _ => None,
    }
}
fn validate_flow(k: &Kernel) -> Result<(), Error> {
    let n = k.blocks.len();
    let mut preds = vec![Vec::new(); n];
    let mut edges = vec![Vec::new(); n];
    for (i, b) in k.blocks.iter().enumerate() {
        match b.terminator {
            Terminator::Return => {}
            Terminator::Jump(t) => edges[i].push(t),
            Terminator::Branch {
                target, otherwise, ..
            } => {
                edges[i].push(target);
                edges[i].push(otherwise);
            }
        }
        for &t in &edges[i] {
            preds[t].push(i);
        }
    }
    let mut reachable = BTreeSet::new();
    let mut queue = VecDeque::from([0]);
    while let Some(i) = queue.pop_front() {
        if reachable.insert(i) {
            queue.extend(&edges[i]);
        }
    }
    if reachable.len() != n {
        return Err(fail(1, "unreachable blocks outside profile"));
    }
    let all: BTreeSet<String> = k.registers.keys().cloned().collect();
    let mut outs = vec![all.clone(); n];
    let mut ins = vec![BTreeSet::new(); n];
    loop {
        let mut changed = false;
        for i in 0..n {
            let input = if i == 0 {
                BTreeSet::new()
            } else {
                preds[i]
                    .iter()
                    .map(|&p| outs[p].clone())
                    .reduce(|a, b| a.intersection(&b).cloned().collect())
                    .unwrap_or_default()
            };
            let mut output = input.clone();
            for inst in &k.blocks[i].instructions {
                if let Some(d) = definition(&inst.kind) {
                    output.insert(d.into());
                }
            }
            if outs[i] != output {
                changed = true;
                outs[i] = output;
            }
            ins[i] = input;
        }
        if !changed {
            break;
        }
    }
    for (i, b) in k.blocks.iter().enumerate() {
        let mut available = ins[i].clone();
        for inst in &b.instructions {
            if reads(&inst.kind).iter().any(|n| !available.contains(*n)) {
                return Err(fail(inst.line, "register not initialized on every path"));
            }
            if let Some(d) = definition(&inst.kind) {
                available.insert(d.into());
            }
        }
        if let Terminator::Branch { predicate, .. } = &b.terminator {
            if !available.contains(predicate) {
                return Err(fail(b.line, "predicate not initialized"));
            }
        }
    }
    Ok(())
}
