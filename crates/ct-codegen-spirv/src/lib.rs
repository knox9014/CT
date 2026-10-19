use ct_ptx::{Error, InstructionKind, Kernel, Op, Param, ParamKind, Terminator, Ty, Value};
use std::collections::BTreeMap;
pub struct Compiled {
    pub entry: String,
    pub params: Vec<Param>,
    pub spirv: Vec<u8>,
}
mod emit;
pub fn translate(source: &str) -> Result<Compiled, Error> {
    let k = ct_ptx::parse(source)?;
    let spirv = emit::generate(&k);
    Ok(Compiled {
        entry: k.name,
        params: k.params,
        spirv,
    })
}
