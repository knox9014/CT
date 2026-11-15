use std::collections::BTreeMap;
use std::sync::Arc;

/// Bounded static Workgroup storage per kernel. Dynamic shared memory is separate.
pub const MAX_STATIC_SHARED_BYTES: u32 = 16_384;
pub const MAX_IDENTIFIER_BYTES: usize = 256;

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
    /// Symbolic per-CTA object; numeric register value is its relative byte offset.
    Shared(String),
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
    Fma,
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
    CvtaShared,
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
    SharedLoad {
        ty: Ty,
        dst: String,
        address: Value,
        offset: u64,
        volatile: bool,
    },
    SharedStore {
        ty: Ty,
        address: Value,
        offset: u64,
        value: Value,
        volatile: bool,
    },
    /// Entire CTA, barrier ID zero; all control decisions must be CTA-uniform.
    BlockBarrier,
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
    pub shared: Vec<Shared>,
    pub name: String,
    pub params: Vec<Param>,
    pub registers: BTreeMap<String, Ty>,
    pub blocks: Vec<Block>,
}
impl Kernel {
    /// Revalidate symbolic shared addresses, returning the exact object per access.
    pub fn shared_access_roots(&self) -> Result<Vec<Option<usize>>, Error> {
        shared::validate(self)
    }
    /// Every control decision must be uniform within a CTA, including backedges.
    pub fn validate_block_barriers(&self) -> Result<(), Error> {
        if self
            .blocks
            .iter()
            .flat_map(|b| &b.instructions)
            .any(|i| matches!(i.kind, InstructionKind::BlockBarrier))
        {
            uniform::validate(self)?;
        }
        Ok(())
    }
}
#[derive(Clone, Debug)]
pub struct Shared {
    pub name: String,
    pub bytes: u32,
    pub alignment: u32,
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
mod alignment;
mod parser;
mod shared;
mod uniform;
pub use parser::{parse, parse_module};
