//! CPU metadata only. Variable storage and address resolution are unsupported.
use crate::registration::copy_name;
#[derive(Clone, Copy, PartialEq, Eq)]
pub struct VariableMetadata {
    pub external: i32,
    pub size: usize,
    pub constant: i32,
    pub global: i32,
}
pub struct Variable {
    pub host: usize,
    pub address: Vec<u8>,
    pub name: Vec<u8>,
    pub metadata: VariableMetadata,
}
pub unsafe fn prepare(
    host: usize,
    address: *const u8,
    name: *const u8,
    metadata: VariableMetadata,
    limit: usize,
) -> Result<Variable, i32> {
    if host == 0
        || metadata.size == 0
        || ![metadata.external, metadata.constant, metadata.global]
            .iter()
            .all(|v| matches!(v, 0 | 1))
    {
        return Err(1);
    }
    if metadata.size > 16 * 1024 * 1024
        || metadata.external != 0
        || metadata.constant != 0
        || metadata.global != 0
    {
        return Err(801);
    }
    let address = unsafe { copy_name(address, limit) }?;
    let name = unsafe { copy_name(name, limit) }?;
    if address != name {
        return Err(801);
    }
    Ok(Variable {
        host,
        address,
        name,
        metadata,
    })
}
#[cfg(test)]
thread_local! {pub static PREPARE_BARRIER:std::cell::RefCell<Option<(std::sync::Arc<std::sync::Barrier>,std::sync::Arc<std::sync::Barrier>)>>=const {std::cell::RefCell::new(None)};}
