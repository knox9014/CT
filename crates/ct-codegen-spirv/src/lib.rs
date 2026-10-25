use ct_ptx::{Error, InstructionKind, Kernel, Op, Param, ParamKind, Terminator, Ty, Value};
use ct_ptx::{Global, GlobalStorage};
use std::collections::BTreeMap;
use std::sync::Arc;
pub struct Compiled {
    pub profile: ct_ptx::Profile,
    pub globals: Arc<[Global]>,
    pub entry: String,
    pub params: Vec<Param>,
    pub spirv: Vec<u8>,
}
pub struct CompiledEntry {
    pub entry: String,
    pub params: Vec<Param>,
}
pub struct CompiledModule {
    pub profile: ct_ptx::Profile,
    pub globals: Arc<[Global]>,
    pub entries: Vec<CompiledEntry>,
    pub spirv: Vec<u8>,
}
mod emit;
pub fn translate_module(source: &str) -> Result<CompiledModule, Error> {
    let module = ct_ptx::parse_module(source)?;
    let spirv = emit::generate_module(&module.kernels)?;
    Ok(CompiledModule {
        profile: module.profile,
        globals: module.globals,
        entries: module
            .kernels
            .into_iter()
            .map(|kernel| CompiledEntry {
                entry: kernel.name,
                params: kernel.params,
            })
            .collect(),
        spirv,
    })
}
pub fn translate(source: &str) -> Result<Compiled, Error> {
    let k = ct_ptx::parse(source)?;
    let spirv = emit::generate(&k)?;
    Ok(Compiled {
        profile: k.profile,
        globals: k.globals,
        entry: k.name,
        params: k.params,
        spirv,
    })
}
