use std::collections::BTreeMap;
use std::sync::Arc;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum GlobalStorage {
    MutableU32 {
        initializer: u32,
    },
    MutableU64 {
        initializer: u64,
    },
    /// A declared name whose storage is outside the implemented profile.
    Unsupported,
}
impl GlobalStorage {
    pub fn storage_type(&self) -> Option<Ty> {
        match self {
            Self::MutableU32 { .. } => Some(Ty::U32),
            Self::MutableU64 { .. } => Some(Ty::U64),
            Self::Unsupported => None,
        }
    }
    pub fn byte_size(&self) -> Option<usize> {
        self.storage_type()
            .map(|t| if t == Ty::U64 { 8 } else { 4 })
    }
    pub fn alignment(&self) -> Option<usize> {
        self.byte_size()
    }
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Global {
    pub name: String,
    pub storage: GlobalStorage,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Ty {
    Pred,
    U32,
    U64,
    F32,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ParamKind {
    Pointer,
    U32,
    U64,
    F32,
}
#[derive(Clone, Debug)]
pub struct Param {
    pub name: String,
    pub kind: ParamKind,
    pub alignment: u32,
}
#[derive(Clone, Debug)]
pub enum Value {
    Reg(String),
    Global(String),
    /// SPIR-V builtin vector kind and scalar component (0=x, 1=y, 2=z).
    Builtin(u32, u32),
    Bits(Ty, u64),
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Op {
    Mov,
    Add,
    Sub,
    Mul,
    MulWide,
    SignedMulWide,
    Mad,
    Div,
    Rem,
    Min { signed: bool },
    Max { signed: bool },
    Abs,
    Neg,
    Ge,
    SignedGe,
    SignedLt,
    Lt,
    Eq,
    Ne,
    Gt,
    Le,
    SignedGt,
    SignedLe,
    Select,
    Cvta,
    Convert { to: Ty, signed: bool },
    And,
    Or,
    Xor,
    Not,
    Shl,
    Shr,
    SignedShr,
}
#[derive(Clone, Debug)]
pub enum InstructionKind {
    Param {
        dst: String,
        index: usize,
    },
    Compute {
        dst: String,
        op: Op,
        ty: Ty,
        args: Vec<Value>,
    },
    Load {
        ty: Ty,
        dst: String,
        address: Value,
        offset: u64,
        volatile: bool,
    },
    Store {
        ty: Ty,
        address: Value,
        offset: u64,
        value: Value,
        volatile: bool,
    },
}
#[derive(Clone, Debug)]
pub struct Instruction {
    pub line: usize,
    pub kind: InstructionKind,
}
#[derive(Clone, Debug)]
pub enum Terminator {
    Return,
    Jump(usize),
    Branch {
        predicate: String,
        negated: bool,
        target: usize,
        otherwise: usize,
    },
}
#[derive(Clone, Debug)]
pub struct Block {
    pub instructions: Vec<Instruction>,
    pub terminator: Terminator,
    pub line: usize,
}
#[derive(Clone, Debug)]
pub struct Kernel {
    pub profile: Profile,
    pub globals: Arc<[Global]>,
    pub name: String,
    pub params: Vec<Param>,
    pub registers: BTreeMap<String, Ty>,
    pub blocks: Vec<Block>,
}
#[derive(Clone, Debug)]
pub struct Module {
    pub profile: Profile,
    pub globals: Arc<[Global]>,
    pub kernels: Vec<Kernel>,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Profile {
    pub major: u16,
    pub minor: u16,
    pub target: u32,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Error {
    pub line: usize,
    pub unsupported: bool,
    pub message: &'static str,
}
impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "line {}: {}", self.line, self.message)
    }
}
impl std::error::Error for Error {}
mod parser;
pub use parser::{parse, parse_module};
